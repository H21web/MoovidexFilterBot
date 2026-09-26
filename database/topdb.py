from info import OTHER_DB_URI
import motor.motor_asyncio
import uuid  # for generating unique IDs

class JsTopDB:
    def __init__(self, db_uri):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(db_uri)
        self.db = self.client["movie_series_db"]
        self.collection = self.db["movie_series"]

    async def set_movie_series_names(self, names, group_id):
        # Split the input string by comma to get individual names
        movie_series_list = names.split(",")
        # Store each name in the database for the group with a unique search_id
        for name in movie_series_list:
            search_id = str(uuid.uuid4())  # Generate unique search_id
            await self.collection.update_one(
                {"name": name.strip(), "group_id": group_id},
                {"$inc": {"search_count": 1}},
                upsert=True
            )

    async def get_movie_series_names(self, group_id):
        # Retrieve all movie and series names for the specified group from the database
        cursor = self.collection.find({"group_id": group_id})
        # Sort by search_count field in descending order
        cursor.sort("search_count", -1)
        names = [document["name"] async for document in cursor]
        return names

    async def clear_movie_series_names(self, group_id):
        # Remove all movie and series names for the specified group from the database
        await self.collection.delete_many({"group_id": group_id})
