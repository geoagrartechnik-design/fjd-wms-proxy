
from flask import Flask, request, Response
from xml.sax.saxutils import escape
from PIL import Image, ImageDraw
import io

app = Flask(__name__)

@app.route("/")
def home():
    return "FJD WMS Testserver läuft!"

@app.route("/wms")
def wms():
    action = request.args.get("REQUEST", "GetCapabilities").lower()

    if action == "getcapabilities":
        url = escape(request.url_root.rstrip("/") + "/wms?")
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<WMT_MS_Capabilities version="1.1.1"
xmlns:xlink="http://www.w3.org/1999/xlink">
<Service>
<Name>OGC:WMS</Name>
<Title>FJD Testserver</Title>
<OnlineResource xlink:type="simple" xlink:href="{url}"/>
</Service>
<Capability>
<Request>
<GetCapabilities>
<Format>application/vnd.ogc.wms_xml</Format>
<DCPType><HTTP><Get>
<OnlineResource xlink:type="simple" xlink:href="{url}"/>
</Get></HTTP></DCPType>
</GetCapabilities>
<GetMap>
<Format>image/png</Format>
<DCPType><HTTP><Get>
<OnlineResource xlink:type="simple" xlink:href="{url}"/>
</Get></HTTP></DCPType>
</GetMap>
</Request>
<Layer>
<Title>Testkarte</Title>
<SRS>EPSG:4326</SRS>
<LatLonBoundingBox minx="7" miny="47" maxx="11" maxy="50"/>
<Layer queryable="0">
<Name>testpunkte</Name>
<Title>Weisse Testpunkte</Title>
<SRS>EPSG:4326</SRS>
<LatLonBoundingBox minx="7" miny="47" maxx="11" maxy="50"/>
</Layer>
</Layer>
</Capability>
</WMT_MS_Capabilities>'''
        return Response(xml, content_type="application/vnd.ogc.wms_xml")

    if action == "getmap":
        w = max(1, min(2048, int(request.args.get("WIDTH", 256))))
        h = max(1, min(2048, int(request.args.get("HEIGHT", 256))))
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for x in range(20, w, 80):
            for y in range(20, h, 80):
                draw.ellipse((x-5, y-5, x+5, y+5),
                             fill="white", outline="black", width=2)
        output = io.BytesIO()
        img.save(output, format="PNG")
        return Response(output.getvalue(), mimetype="image/png")

    return Response("Unsupported request", status=400)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
