from flask import Flask, request, Response
import requests
import xml.etree.ElementTree as ET
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

LGL = 'https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ALKIS_Grenzpunkte_Koordinatenqualitaet'
SESSION = requests.Session()

@app.get('/')
def home():
    return 'FJD BW Grenzpunkte Proxy läuft!'

@app.get('/wms')
def wms():
    # WMS parameter names are case-insensitive. Preserve values and avoid duplicate keys.
    params = {k.upper(): v for k, v in request.args.items()}
    action = params.get('REQUEST', 'GetCapabilities')
    params['SERVICE'] = 'WMS'
    params['REQUEST'] = action

    if action.lower() == 'getcapabilities':
        # WMS 1.1.1 is supported by many agricultural mapping clients.
        params['VERSION'] = '1.1.1'
    elif action.lower() == 'getmap':
        params.setdefault('VERSION', '1.1.1')
        params.setdefault('LAYERS', 'nora:v_al_grenzpunkt_q')
        params.setdefault('STYLES', '')
        params.setdefault('FORMAT', 'image/png')
        params.setdefault('TRANSPARENT', 'TRUE')
        # WMS 1.1.1 uses SRS; WMS 1.3.0 uses CRS. Do not change BBOX/axis order.
        if params['VERSION'] == '1.3.0' and 'CRS' not in params and 'SRS' in params:
            params['CRS'] = params.pop('SRS')
        elif params['VERSION'] != '1.3.0' and 'SRS' not in params and 'CRS' in params:
            params['SRS'] = params.pop('CRS')

    try:
        upstream = SESSION.get(LGL, params=params, timeout=(10, 45))
        app.logger.info('WMS %s status=%s type=%s', action, upstream.status_code, upstream.headers.get('Content-Type'))
        content = upstream.content
        content_type = upstream.headers.get('Content-Type', 'application/octet-stream')

        if action.lower() == 'getcapabilities' and upstream.ok:
            root = ET.fromstring(content)
            endpoint = request.url_root.rstrip('/') + '/wms?'
            for element in root.iter():
                if element.tag.rsplit('}', 1)[-1] == 'OnlineResource':
                    for key in list(element.attrib):
                        if key.rsplit('}', 1)[-1] == 'href':
                            element.set(key, endpoint)
            content = ET.tostring(root, encoding='utf-8', xml_declaration=True)
            content_type = 'text/xml; charset=utf-8'

        return Response(content, status=upstream.status_code, headers={
            'Content-Type': content_type,
            'Cache-Control': 'public, max-age=120' if action.lower() == 'getmap' and upstream.ok else 'no-store',
            'Access-Control-Allow-Origin': '*',
        })
    except requests.RequestException as exc:
        app.logger.exception('Upstream WMS request failed')
        return Response('WMS upstream request failed: ' + str(exc), status=502, content_type='text/plain')
    except ET.ParseError:
        app.logger.exception('Invalid capabilities XML from upstream')
        return Response('Invalid capabilities XML from upstream', status=502, content_type='text/plain')
