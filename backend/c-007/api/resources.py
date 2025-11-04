from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate
import store


blp = Blueprint(
    "items",
    __name__,
    description="Item operations with OpenAPI schema",
    url_prefix="/api",
)


class HelloSchema(Schema):
    message = fields.String(required=True, example="Hello world")


class ItemInSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1), example="Widget")
    price = fields.Float(required=True, validate=validate.Range(min=0), example=9.99)
    tags = fields.List(fields.String(), required=False, example=["tools", "sale"])


class ItemOutSchema(ItemInSchema):
    id = fields.Integer(required=True, example=1)


@blp.route("/hello")
@blp.response(200, HelloSchema)
def hello():
    name = request.args.get("name", "world")
    return {"message": f"Hello {name}"}


@blp.route("/items")
class ItemsResource(MethodView):
    @blp.response(200, ItemOutSchema(many=True))
    def get(self):
        return store.get_items()

    @blp.arguments(ItemInSchema)
    @blp.response(201, ItemOutSchema)
    def post(self, json_data):
        item = store.add_item(
            name=json_data["name"],
            price=json_data["price"],
            tags=json_data.get("tags") or [],
        )
        return item

