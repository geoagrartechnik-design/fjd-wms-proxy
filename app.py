
from flask import Flask, request, Response
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

LGL = (
    "https://owsproxy.lgl-bw.de/owsproxy/ows/"
    "WMS_LGL-BW_ALKIS_Grenzpunkte_Koordinatenqualitaet"
)

@app.route("/")
def home():
    return "FJD BW Grenzpunkte Proxy läuft!"

@app.route("/wms")
def wms():
    params = request.args.to_dict(flat=True)
    action = params.get("REQUEST", params.get("request", "GetCapabilities"))
    params["SERVICE"] = "WMS"
    params["REQUEST"] = action

    if action.lower() == "getcapabilities":
        params["VERSION"] = "1.1.1"

    try:
        r = requests.get(LGL, params=params, timeout=45)
        r.raise_for_status()

        content = r.content
        content_type = r.headers.get(
            "Content-Type", "application/octet-stream"
        )

        if action.lower() == "getcapabilities":
            root = ET.fromstring(content)

            for element in root.iter():
                if element.tag.split("}")[-1] in ("OnlineResource",):
                    for key in list(element.attrib):
                        if key.endswith("}href") or key == "href":
                            element.set(
                                key,
                                request.url_root.rstrip("/") + "/wms?"
                            )

            content = ET.tostring(
                root, encoding="utf-8", xml_declaration=True
            )
            content_type = "text/xml"

        return Response(content, content_type=content_type)

    except Exception as e:
        return Response(
            "Proxy-Fehler: " + str(e),
            status=502,
            content_type="text/plain"
        )
