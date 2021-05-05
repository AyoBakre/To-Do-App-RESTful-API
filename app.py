import os
from flask import Flask
from flask_restful import Api, Resource, reqparse, abort
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow


# init app
app = Flask(__name__)
api = Api(app)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
db = SQLAlchemy(app)
ma = Marshmallow(app)


class ToDo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(200), default="", index=True)
    status = db.Column(db.Boolean, default=False, index=True)


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


# shows a list of all todos, and lets you POST to add new tasks
class TodoList(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('title', type=str, required=True,
                                   help='No task title provided',
                                   location='json')
        self.reqparse.add_argument('description', type=str, location='json')
        super(TodoList, self).__init__()

    def get(self):
        tasks = ToDo.query.all()
        return to_dos_schema.dump(tasks)

    def post(self):
        args = self.reqparse.parse_args()
        task = ToDo(title=args['title'], description=args['description'])
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

    def get(self, id):
        task = ToDo.query.get(id)
        if task is None:
            abort(404, message="could not find a task with that id")
        return to_do_schema.dump(task), 201

    def put(self, id):
        task = ToDo.query.get(id)
        if task is None:
            abort(404, message="could not find a task with that id")
        args = self.reqparse.parse_args()
        task.title = args['title'] or task.title
        task.description = args['description'] or task.description
        task.status = args['status'] or task.status
        db.session.commit()
        return to_do_schema.dump(task), 201

    def delete(self, id):
        task = ToDo.query.get(id)
        if task is None:
            abort(404, message="could not find a task with that id")
        db.session.delete(task)
        db.session.commit()
        return {'result': True}, 204


api.add_resource(TodoList, '/todo/api/v1.0/tasks', endpoint='tasks')
api.add_resource(Todo, '/todo/api/v1.0/tasks/<int:id>', endpoint='task')


# run server
if __name__ == '__main__':
    app.run(debug=True)