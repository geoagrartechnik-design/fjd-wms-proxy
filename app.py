"""WMS proxy for FJD Trion / ArcGIS Runtime and LGL BW boundary points."""
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

import requests
from flask import Flask, Response, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

LGL = "https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ALKIS_Grenzpunkte_Koordinatenqualitaet"
LAYER = "nora:v_al_grenzpunkt_q"
HTTP = requests.Session()


@app.get("/")
def home():
    return "FJD BW Grenzpunkte Proxy läuft!"


@app.get("/wms")
def wms():
    # WMS parameter names are case-insensitive; remove duplicate mixed-case keys.
    params = {key.upper(): value for key, value in request.args.items()}
    action = params.get("REQUEST", "GetCapabilities")
    operation = action.lower()
    params["SERVICE"] = "WMS"
    params["REQUEST"] = action

    if operation == "getcapabilities":
        # CRITICAL: Honor the client's requested version. ArcGIS Runtime requests
        # 1.3.0; advertising 1.1.1 in response can trigger repeated retries.
        params["VERSION"] = params.get("VERSION", "1.3.0")
    elif operation == "getmap":
        params.setdefault("VERSION", "1.3.0")
        params.setdefault("LAYERS", LAYER)
        params.setdefault("STYLES", "")
        params.setdefault("FORMAT", "image/png")
        params.setdefault("TRANSPARENT", "TRUE")
        if params["VERSION"] == "1.3.0":
            if "CRS" not in params and "SRS" in params:
                params["CRS"] = params.pop("SRS")
        elif "SRS" not in params and "CRS" in params:
            params["SRS"] = params.pop("CRS")

    app.logger.info("FJD REQUEST operation=%s version=%s crs=%s bbox=%s", action,
                    params.get("VERSION"), params.get("CRS", params.get("SRS")),
                    params.get("BBOX"))

    try:
        upstream = HTTP.get(LGL, params=params, timeout=(10, 45))
        body = upstream.content
        content_type = upstream.headers.get("Content-Type", "application/octet-stream")
        app.logger.info("LGL RESPONSE operation=%s status=%s type=%s bytes=%s",
                        action, upstream.status_code, content_type, len(body))

        if operation == "getcapabilities" and upstream.ok:
            root = ET.fromstring(body)
            actual_version = root.attrib.get("version", "unknown")
            app.logger.info("CAPABILITIES version=%s root=%s", actual_version, root.tag)
            endpoint = request.url_root.rstrip("/") + "/wms?"
            # Both GetCapabilities and GetMap OnlineResource endpoints must point
            # to this proxy, not directly to the original LGL service.
            for element in root.iter():
                if element.tag.rsplit("}", 1)[-1] == "OnlineResource":
                    for attribute in list(element.attrib):
                        if attribute.rsplit("}", 1)[-1] == "href":
                            element.set(attribute, endpoint)
            body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            content_type = "application/xml; charset=utf-8"

        if operation == "getmap" and upstream.ok and "image/" not in content_type.lower():
            app.logger.warning("GetMap did not return an image: %s", body[:400])

        return Response(body, status=upstream.status_code, headers={
            "Content-Type": content_type,
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
        })
    except requests.RequestException as exc:
        app.logger.exception("LGL request failed")
        return Response("LGL request failed: " + str(exc), status=502,
                        content_type="text/plain; charset=utf-8")
    except ET.ParseError as exc:
        app.logger.exception("LGL capabilities XML parsing failed")
        return Response("LGL capabilities XML parsing failed: " + str(exc),
                        status=502, content_type="text/plain; charset=utf-8")
