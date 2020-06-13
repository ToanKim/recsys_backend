from flask import Flask, request, Blueprint
from flask_cors import CORS, cross_origin
app = Flask(__name__)
cors = CORS(app)
api = Blueprint("api", __name__, url_prefix="/api")

### Define CONSTANT ###
USER_ID = '7970B0ED6905783592CF9BD056E26780'
TIME_FORMAT = '%Y-%m-%d %X'

### Utils ###
import re
def format_product_name(name):
    name = name.replace('https://www.sendo.vn/san-pham/', '').replace('/', '')
    formatted_name = re.findall('(.*?)(-(\d*)|(\?.*))*$', name)[0][0]
    return formatted_name

def normalize_product(product_tuple):
    product_id, name = product_tuple
    return {
        "product_id": product_id,
        "name": format_product_name(name)
    }

def normalize_products(products):
    return [normalize_product(product) for product in products]

def to_unix_time(time):
    return time.timestamp()

def get_weight(time_list):
    intial = time_list[0]
    return [1/((float(intial) - float(time) + 1) ** 0.2) for time in time_list]

### Load model ###
from sklearn.neighbors import NearestNeighbors

class myKNN: # define dưới server
    def __init__(self, matrix):
        self.matrix = matrix
        self.model = NearestNeighbors(metric='cosine', algorithm='brute', n_neighbors=20, n_jobs=-1)
    def predict(self, idx, n_neighbors):
        input = self.matrix[[idx]]
        return self.model.kneighbors(input, n_neighbors=5)
    def fit(self, y):
        self.model.fit(self.matrix, y)

import joblib
knn_model = joblib.load('./model/knn_joblib.pkl')

### MySQL ###
import MySQLdb
db = MySQLdb.connect(host="recsys_db", user="root", passwd="rootpassword", db="recsys")
c = db.cursor()

### SQL Query ###
from datetime import datetime
def get_clicks(user_id):
    c.execute("""   SELECT user_clicks.time, user_clicks.product_id, products.belong_cate_lvl3_id  
                    FROM user_clicks, products
                    WHERE user_id = %s AND user_clicks.product_id = products.product_id
                    ORDER BY time DESC
                    LIMIT 25;""", (user_id, ))
    result = c.fetchall()
    return [list(row) for row in result]

def insert_click(user_id, product_id):
    try:
        print(type(product_id))
        current_time = datetime.now().strftime(TIME_FORMAT)
        c.execute("""   INSERT INTO user_clicks (time, user_id, product_id)
                        VALUES (%s, %s, %s)""", (current_time, user_id, product_id))
        db.commit()

        return 'Inserted'
    except Exception as e:
        return e.message

def get_random_products():
    c.execute("""   SELECT product_id, href FROM products
                    ORDER BY RAND ()
                    LIMIT 10;""")
    result = c.fetchall()
    return result

def get_random_products_from_lvl2_id(lvl2_id, limit):
    c.execute("""   SELECT product_id, href
                    FROM products
                    WHERE belong_cate_lvl2_id = %s
                    ORDER BY RAND ()
                    LIMIT %s""", (lvl2_id, limit, ))
    result = c.fetchall()
    return result

def get_lvl2_from_lvl3(lvl3_id):
    c.execute("""   SELECT belong_cate_lvl2_id
                    FROM products
                    WHERE belong_cate_lvl3_id = %s
                    LIMIT 1;""", (lvl3_id, ))
    result = c.fetchone()
    return result[0]

def get_lvl2_index(lvl2_id):
    c.execute("""   SELECT id
                    FROM lvl2_id
                    WHERE lvl2_id = %s""", (lvl2_id, ))
    result = c.fetchone()
    return result[0]

def get_lvl2_from_index(index):
    c.execute("""   SELECT lvl2_id
                    FROM lvl2_id
                    WHERE id = %s""", (index,))

    result = c.fetchone()
    return result[0]

### Routing ###
@api.route('/', methods=['GET'])
def hello_world():
    return 'Hello World'

@api.route('/test', methods=['GET'])
def test_db():
    c.execute("""SELECT * FROM test_connection""")
    result = c.fetchall()
    print(result)
    return dict(result)

@api.route('/click', methods=['POST'])
@cross_origin()
def click():
    payload = request.get_json()
    if 'product_id' in payload:
        return insert_click(USER_ID, payload['product_id'])
    return 'Invalid Request'


@api.route('/home', methods=['GET'])
@cross_origin()
def get_home():
    ### Get random products to display at HOME
    hot_products = get_random_products()

    ### Get recently clicked products of user
    user_clicks = get_clicks(USER_ID)

    # Convert to UNIX time
    for i in range(len(user_clicks)):
        user_clicks[i][0] = to_unix_time(user_clicks[i][0])

    weight = get_weight([user_click[0] for user_click in user_clicks])

    lvl3_list = [user_click[2] for user_click in user_clicks]

    d = dict()
    for i in range(len(lvl3_list)):
        if lvl3_list[i] in d:
            d[lvl3_list[i]] += weight[i]
        else:
            d[lvl3_list[i]] = weight[i]

    sorted_dict = {key: value for key, value in sorted(d.items(), key=lambda item: item[1], reverse=True)}
    lvl3_id_ranking = list(sorted_dict.keys())

    lvl2_id = get_lvl2_from_lvl3(lvl3_id_ranking[0])
    lvl2_index = get_lvl2_index(lvl2_id)
    lvl2_prediction = knn_model.predict(lvl2_index, 5)[1][0]
    lvl2_id_list = [get_lvl2_from_index(index) for index in lvl2_prediction]

    recommendations = list()
    recommendations = recommendations + normalize_products(get_random_products_from_lvl2_id(lvl2_id_list[0], 7))
    recommendations = recommendations + normalize_products(get_random_products_from_lvl2_id(lvl2_id_list[1], 4))
    recommendations = recommendations + normalize_products(get_random_products_from_lvl2_id(lvl2_id_list[4], 5))

    if len(lvl3_id_ranking) > 1:
        lvl2_id_2nd = get_lvl2_from_lvl3(lvl3_id_ranking[1])
        lvl2_index_2nd = get_lvl2_index(lvl2_id_2nd)
        lvl2_prediction_2nd = knn_model.predict(lvl2_index_2nd, 5)[1][0]
        lvl2_id_list_2nd = [get_lvl2_from_index(index) for index in lvl2_prediction_2nd]

        recommendations = recommendations + normalize_products(get_random_products_from_lvl2_id(lvl2_id_list_2nd[0], 6))
        recommendations = recommendations + normalize_products(get_random_products_from_lvl2_id(lvl2_id_list_2nd[1], 3))
        
    print(recommendations)    

    return {
        "hot_products": normalize_products(hot_products),
        "recommendations": recommendations
    }

# Register blueprint
app.register_blueprint(api)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)