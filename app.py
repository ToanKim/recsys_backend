from flask import Flask, Blueprint
app = Flask(__name__)
api = Blueprint("api", __name__, url_prefix="/api")

import MySQLdb
db = MySQLdb.connect(host="recsys_db", user="root", passwd="rootpassword", db="recsys")
c = db.cursor()

@api.route('/', methods=['GET'])
def hello_world():
    return 'Hello World'

@api.route('/test', methods=['GET'])
def test_db():
    c.execute("""SELECT * FROM test_connection""")
    result = c.fetchall()
    print(result)
    return dict(result)



@api.route('/home', methods=['GET'])
def get_home():
    pass


# Register blueprint
app.register_blueprint(api)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)