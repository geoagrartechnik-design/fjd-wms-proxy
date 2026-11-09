
import logging
import xml.etree.ElementTree as ET

import requests
from flask import Flask, Response, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

LGL = (
    "https://owsproxy.lgl-bw.de/owsproxy/ows/"
    "WMS_LGL-BW_ALKIS_Grenzpunkte_Koordinatenqualitaet"
)

LAYER = "nora:v_al_grenzpunkt_q"

NS = "http://www.opengis.net/wms"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("", NS)
ET.register_namespace("xlink", XLINK)
ET.register_namespace("xsi", XSI)


def tag(name):
    return "{%s}%s" % (NS, name)


def add(parent, name, value=None, attrs=None):
    element = ET.SubElement(
        parent, tag(name), attrs or {}
    )
    if value is not None:
        element.text = str(value)
    return element


def resource(parent, url):
    return add(
        parent,
        "OnlineResource",
        attrs={
            "{%s}type" % XLINK: "simple",
            "{%s}href" % XLINK: url
        }
    )


@app.route("/")
def home():
    return "FJD BW Grenzpunkte WMS läuft"


@app.route("/wms")
def wms():
    params = {
        key.upper(): value
        for key, value in request.args.items()
    }

    operation = params.get(
        "REQUEST", "GetCapabilities"
    ).lower()

    app.logger.info(
        "FJD request=%s version=%s crs=%s bbox=%s",
        operation,
        params.get("VERSION"),
        params.get("CRS", params.get("SRS")),
        params.get("BBOX")
    )

    if operation == "getcapabilities":
        version = params.get("VERSION", "1.3.0")

        if version != "1.3.0":
            return legacy_capabilities()

        return capabilities()

    if operation == "getmap":
        params["SERVICE"] = "WMS"
        params["REQUEST"] = "GetMap"
        params.setdefault("LAYERS", LAYER)
        params.setdefault("STYLES", "")
        params.setdefault("FORMAT", "image/png")
        params.setdefault("TRANSPARENT", "TRUE")

        if (
            params.get("VERSION") == "1.3.0"
            and "SRS" in params
            and "CRS" not in params
        ):
            params["CRS"] = params.pop("SRS")

        try:
            response = requests.get(
                LGL,
                params=params,
                timeout=(10, 45)
            )

            app.logger.info(
                "LGL GetMap status=%s type=%s bytes=%s",
                response.status_code,
                response.headers.get("Content-Type"),
                len(response.content)
            )

            return Response(
                response.content,
                status=response.status_code,
                content_type=response.headers.get(
                    "Content-Type",
                    "application/octet-stream"
                )
            )

        except requests.RequestException as exc:
            app.logger.exception("GetMap failed")

            return Response(
                str(exc),
                status=502,
                content_type="text/plain"
            )

    return Response(
        "Unsupported WMS request",
        status=400,
        content_type="text/plain"
    )


def capabilities():
    url = request.url_root.rstrip("/") + "/wms?"

    root = ET.Element(
        tag("WMS_Capabilities"),
        {
            "version": "1.3.0",
            "{%s}schemaLocation" % XSI:
                NS + " https://schemas.opengis.net/"
                "wms/1.3.0/capabilities_1_3_0.xsd"
        }
    )

    service = add(root, "Service")
    add(service, "Name", "WMS")
    add(service, "Title", "BW ALKIS Grenzpunkte")
    add(
        service,
        "Abstract",
        "Grenzpunkte Baden-Wuerttemberg, LGL BW"
    )
    resource(service, url)

    capability = add(root, "Capability")
    requests_node = add(capability, "Request")

    operations = [
        ("GetCapabilities", ["text/xml"]),
        ("GetMap", ["image/png", "image/jpeg"])
    ]

    for name, formats in operations:
        operation = add(requests_node, name)

        for fmt in formats:
            add(operation, "Format", fmt)

        dcp = add(operation, "DCPType")
        http = add(dcp, "HTTP")
        get = add(http, "Get")
        resource(get, url)

    exception = add(capability, "Exception")
    add(exception, "Format", "XML")

    parent = add(capability, "Layer")
    add(parent, "Title", "BW Grenzpunkte")

    for crs in [
        "EPSG:3857",
        "EPSG:25832",
        "EPSG:4326"
    ]:
        add(parent, "CRS", crs)

    layer = add(
        parent,
        "Layer",
        attrs={
            "queryable": "0",
            "opaque": "0",
            "noSubsets": "0"
        }
    )

    add(layer, "Name", LAYER)
    add(
        layer,
        "Title",
        "ALKIS Grenzpunkte Koordinatenqualitaet"
    )
    add(
        layer,
        "Abstract",
        "Originale Grenzpunkte des LGL BW"
    )

    bbox = add(layer, "EX_GeographicBoundingBox")
    add(bbox, "westBoundLongitude", "7.4")
    add(bbox, "eastBoundLongitude", "10.6")
    add(bbox, "southBoundLatitude", "47.5")
    add(bbox, "northBoundLatitude", "49.9")

    content = ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True
    )

    return Response(
        content,
        content_type="text/xml; charset=utf-8"
    )


def legacy_capabilities():
    try:
        response = requests.get(
            LGL,
            params={
                "SERVICE": "WMS",
                "REQUEST": "GetCapabilities",
                "VERSION": "1.1.1"
            },
            timeout=(10, 45)
        )

        response.raise_for_status()
        root = ET.fromstring(response.content)

        url = request.url_root.rstrip("/") + "/wms?"

        for element in root.iter():
            if (
                element.tag.rsplit("}", 1)[-1]
                == "OnlineResource"
            ):
                for key in element.attrib:
                    if (
                        key.rsplit("}", 1)[-1]
                        == "href"
                    ):
                        element.set(key, url)

        content = ET.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True
        )

        return Response(
            content,
            content_type="text/xml; charset=utf-8"
        )

    except (
        requests.RequestException,
        ET.ParseError
    ) as exc:
        app.logger.exception(
            "Legacy capabilities failed"
        )

        return Response(
            str(exc),
            status=502,
            content_type="text/plain"
        )
