
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

HTTP = requests.Session()


@app.route("/")
def home():
    return "FJD BW Grenzpunkte Proxy läuft!"


@app.route("/wms")
def wms():
    params = {
        k.upper(): v
        for k, v in request.args.items()
    }

    action = params.get("REQUEST", "GetCapabilities")
    operation = action.lower()

    params["SERVICE"] = "WMS"
    params["REQUEST"] = action

    if operation == "getcapabilities":
        params["VERSION"] = "1.1.1"

    elif operation == "getmap":
        version = params.get("VERSION", "1.1.1")

        if version == "1.3.0":
            if "CRS" not in params and "SRS" in params:
                params["CRS"] = params.pop("SRS")

        else:
            if "SRS" not in params and "CRS" in params:
                params["SRS"] = params.pop("CRS")

    app.logger.info(
        "FJD %s version=%s crs=%s bbox=%s",
        action,
        params.get("VERSION"),
        params.get("CRS", params.get("SRS")),
        params.get("BBOX")
    )

    try:
        upstream = HTTP.get(
            LGL,
            params=params,
            timeout=(10, 45)
        )

        upstream.raise_for_status()

        body = upstream.content

        content_type = upstream.headers.get(
            "Content-Type",
            "application/octet-stream"
        )

        if operation == "getcapabilities":
            root = ET.fromstring(body)

            proxy_url = (
                request.url_root.rstrip("/") + "/wms?"
            )

            for element in root.iter():
                if element.tag.rsplit("}", 1)[-1] == "OnlineResource":
                    for attribute in list(element.attrib):
                        if attribute.rsplit("}", 1)[-1] == "href":
                            element.set(attribute, proxy_url)

            body = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True
            )

            content_type = "text/xml"

        app.logger.info(
            "WMS %s status=200 type=%s bytes=%d",
            action,
            content_type,
            len(body)
        )

        return Response(
            body,
            status=200,
            content_type=content_type
        )

    except (requests.RequestException, ET.ParseError) as exc:
        app.logger.exception(
            "WMS error for %s",
            action
        )

        return Response(
            "Proxy-Fehler: " + str(exc),
            status=502,
            content_type="text/plain"
        )
