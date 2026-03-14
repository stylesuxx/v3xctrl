from flask_smorest import Api

from .camera import blueprint as camera_blueprint
from .config import blueprint as config_blueprint
from .gpio import blueprint as gpio_blueprint
from .modem import blueprint as modem_blueprint
from .service import blueprint as service_blueprint
from .system import blueprint as system_blueprint


def register_routes(api: Api) -> None:
    api.register_blueprint(modem_blueprint)
    api.register_blueprint(service_blueprint)
    api.register_blueprint(system_blueprint)
    api.register_blueprint(config_blueprint)
    api.register_blueprint(gpio_blueprint)
    api.register_blueprint(camera_blueprint)
