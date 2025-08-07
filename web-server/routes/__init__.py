from flask_smorest import Api

from .modem import blueprint as modem_blueprint
from .service import blueprint as service_blueprint
from .streamer import blueprint as streamer_blueprint
from .config import blueprint as config_blueprint
from .gpio import blueprint as gpio_blueprint


def register_routes(api: Api) -> None:
    api.register_blueprint(modem_blueprint)
    api.register_blueprint(service_blueprint)
    api.register_blueprint(streamer_blueprint)
    api.register_blueprint(config_blueprint)
    api.register_blueprint(gpio_blueprint)
