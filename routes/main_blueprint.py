from flask import Blueprint, render_template


main_bp = Blueprint('main_blueprint', __name__)


@main_bp.route('/')
def index():
    # return "This is an example main blue print app"
    return render_template('index.html')


@main_bp.route('/services')
def service():
    # return render_template('service.html', username=current_user.username)
    return render_template('service.html')