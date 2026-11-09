
from flask import Flask, request, Response
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

SOURCE = (
    "https://owsproxy.lgl-bw.de/owsproxy/ows/"
    "WMS_LGL-BW_ALKIS_Basis_Vertrieb"
)

@app.route("/")
def home():
    return "FJD BW WMS Proxy laeuft!"

@app.route("/wms")
def wms():
    params = dict(request.args)
    action = params.get(
        "REQUEST",
        params.get("request", "GetCapabilities")
    ).lower()

    # Parameter vereinheitlichen
    params = {k.upper(): v for k, v in params.items()}
    params["SERVICE"] = "WMS"

    if action == "getcapabilities":
        params["REQUEST"] = "GetCapabilities"
        params["VERSION"] = "1.1.1"

    elif action == "getmap":
        params["REQUEST"] = "GetMap"
        params["VERSION"] = "1.1.1"

    else:
        return Response(
            "Unsupported WMS request",
            status=400
        )

    try:
        upstream = requests.get(
            SOURCE,
            params=params,
            timeout=35
        )
        upstream.raise_for_status()

        content = upstream.content
        content_type = upstream.headers.get(
            "Content-Type",
            "application/octet-stream"
        )

        if action == "getcapabilities":
            root = ET.fromstring(content)

            proxy_url = request.url_root.rstrip("/") + "/wms?"

            for element in root.iter():
                for key, value in list(element.attrib.items()):
                    if key.endswith("href") and (
                        "owsproxy.lgl-bw.de" in value
                    ):
                        element.set(key, proxy_url)

            content = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True
            )
            content_type = "text/xml"

        return Response(
            content,
            content_type=content_type,
            status=upstream.status_code
        )

    except requests.RequestException as error:
        app.logger.error("WMS upstream: %s", error)
        return Response(
            "BW WMS upstream unavailable",
            status=502
        )

    except ET.ParseError as error:
        app.logger.error("Invalid upstream XML: %s", error)
        return Response(
            "BW WMS returned invalid XML",
            status=502
        )
