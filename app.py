import os
import datetime
from flask import Flask
from flask_restful import Api, Resource, reqparse, abort
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_jwt_extended import create_access_token


# init app
app = Flask(__name__)
api = Api(app)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["JWT_SECRET_KEY"] = 't1NP63m4wnBg6nyHYKfmc2TpCOGI4nss'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
db = SQLAlchemy(app)
ma = Marshmallow(app)
jwt = JWTManager(app)


class ToDo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(200), default="", index=True)
    status = db.Column(db.Boolean, default=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class User(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    username = db.Column(db.String(32), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    tasks = db.relationship('ToDo', backref='author', lazy='dynamic')

    def hash_password(self, password):
        self.password_hash = generate_password_hash(password).decode('utf8')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# schema
class ToDoSchema(ma.Schema):
    class Meta:
        fields = ('links', 'title', 'description', 'status')

    links = ma.Hyperlinks(
        {
            "self": ma.URLFor("tasks", values=dict(id="<id>")),
            "collection": ma.URLFor("tasks"),
        }
    )


to_do_schema = ToDoSchema()
to_dos_schema = ToDoSchema(many=True)


# user schema
class UserSchema(ma.Schema):
    class Meta:
        fields = ('username',)


user_schema = UserSchema()
users_schema = UserSchema(many=True)


# shows a list of all todos, and lets you POST to add new tasks
class TodoList(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('title', type=str, required=True,
                                   help='No task title provided',
                                   location='json')
        self.reqparse.add_argument('description', type=str, location='json')
        super(TodoList, self).__init__()

    @jwt_required()
    def get(self):
        tasks = ToDo.query.all()
        return to_dos_schema.dump(tasks)

    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        args = self.reqparse.parse_args()
        task = ToDo(title=args['title'], description=args['description'], author=user)
        db.session.add(task)
        db.session.commit()
        return to_do_schema.dump(task), 201


class Todo(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('title', type=str,
                                   location='json')
        self.reqparse.add_argument('description', type=str, location='json')
        self.reqparse.add_argument('status', type=bool, location='json')
        super(Todo, self).__init__()

    @jwt_required()
    def get(self, task_id):
        task = ToDo.query.filter_by(id=task_id).first()
        if task is None:
            abort(404, message="could not find a task with that id")
        return to_do_schema.dump(task), 201

    @jwt_required()
    def put(self, task_id):
        task = ToDo.query.filter_by(id=task_id).first()
        if task is None:
            abort(404, message="could not find a task with that id")
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        if task.author is not user:
            abort(404, message="can only edit your own task")
        args = self.reqparse.parse_args()
        task.title = args['title'] or task.title
        task.description = args['description'] or task.description
        task.status = args['status'] or task.status
        db.session.commit()
        return to_do_schema.dump(task), 201

    @jwt_required()
    def delete(self, task_id):
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        task = ToDo.query.filter_by(id=task_id).first()
        if task.author is not user:
            abort(404, message="can only delete your own task")
        if task is None:
            abort(404, message="could not find a task with that id")
        db.session.delete(task)
        db.session.commit()
        return {'result': True}, 204


class SignUp(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('username', type=str,
                                   location='json', required=True, help="Username is required")
        self.reqparse.add_argument('password', type=str, location='json', required=True, help="password is required")
        super(SignUp, self).__init__()

    def post(self):
        args = self.reqparse.parse_args()
        if User.query.filter_by(username=args['username']).first() is not None:
            abort(400, message="existing user")  # existing user
        new_user = User(username=args['username'])
        new_user.hash_password(args['password'])
        db.session.add(new_user)
        db.session.commit()
        return user_schema.dump(new_user), 200


class SignIn(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('username', type=str,
                                   location='json', required=True, help="Username is required")
        self.reqparse.add_argument('password', type=str, location='json', required=True, help="password is required")
        super(SignIn, self).__init__()

    def post(self):
        args = self.reqparse.parse_args()
        user = User.query.filter_by(username=args['username']).first()
        if user is None:
            abort(404, message="user does not exist")  # existing user
        authorized = user.check_password(args['password'])
        if not authorized:
            return {'error': 'username or password invalid'}, 401
        expires = datetime.timedelta(days=7)
        access_token = create_access_token(identity=str(user.id), expires_delta=expires)

        return {'token': access_token}, 200


api.add_resource(TodoList, '/todo/api/v1.0/tasks', endpoint='tasks')
api.add_resource(Todo, '/todo/api/v1.0/tasks/<int:task_id>', endpoint='task')
api.add_resource(SignUp, '/todo/api/v1.0/users/signup', endpoint='user_sign_up')
api.add_resource(SignIn, '/todo/api/v1.0/users/signin', endpoint='user_sign_in')


# run server
if __name__ == '__main__':
    app.run(debug=True)