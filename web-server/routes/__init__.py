from .modem import modem_blueprint


def register_routes(app):
    app.register_blueprint(modem_blueprint)
