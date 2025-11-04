from ariadne import QueryType, MutationType, make_executable_schema, gql
from graphql import print_schema as graphql_print_schema
from graphql import get_introspection_query, graphql_sync as graphql_core_sync
import store


type_defs = gql(
    """
    type Query {
      hello(name: String): String!
      items: [Item!]!
    }

    type Mutation {
      addItem(item: NewItem!): Item!
    }

    type Item {
      id: ID!
      name: String!
      price: Float!
      tags: [String!]!
    }

    input NewItem {
      name: String!
      price: Float!
      tags: [String!]
    }
    """
)

query = QueryType()
mutation = MutationType()


@query.field("hello")
def resolve_hello(*_, name=None):
    target = name or "world"
    return f"Hello {target}"


@query.field("items")
def resolve_items(*_):
    return store.get_items()


@mutation.field("addItem")
def resolve_add_item(*_, item):
    created = store.add_item(name=item["name"], price=item["price"], tags=item.get("tags") or [])
    return created


schema = make_executable_schema(type_defs, query, mutation)


def get_sdl() -> str:
    return str(graphql_print_schema(schema))


def get_introspection() -> dict:
    q = get_introspection_query()
    result = graphql_core_sync(schema, q)
    if result.errors:
        raise RuntimeError(str(result.errors))
    return result.data

