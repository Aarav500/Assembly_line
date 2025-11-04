import serverless_wsgi
from wsgi import app

def handler(event, context):
    return serverless_wsgi.handle_request(app, event, context)

