
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_NAME, USER_DB_URI

class RequestsDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.requests

    async def add_request(self, user_id, user_name, content, message_id=None):
        request_data = {
            "user_id": user_id,
            "user_name": user_name,
            "content": content,
            "status": "pending",  # pending, fulfilled, rejected
            "request_date": datetime.datetime.now(),
            "message_id": message_id  # ID of the message in the REQST_CHANNEL
        }
        result = await self.col.insert_one(request_data)
        return result.inserted_id

    async def get_all_requests(self, page=1, limit=50, status=None):
        skip = (page - 1) * limit
        query = {}
        if status:
            query["status"] = status
            
        cursor = self.col.find(query).sort("request_date", -1).skip(skip).limit(limit)
        requests = await cursor.to_list(length=limit)
        return requests

    async def get_total_requests_count(self, status=None):
        query = {}
        if status:
            query["status"] = status
        count = await self.col.count_documents(query)
        return count

    async def update_request_status(self, request_id, status):
        from bson.objectid import ObjectId
        try:
            result = await self.col.update_one(
                {"_id": ObjectId(request_id)},
                {"$set": {"status": status}}
            )
            return result.matched_count > 0
        except Exception:
            return False
    
    async def get_request(self, request_id):
        from bson.objectid import ObjectId
        try:
            return await self.col.find_one({"_id": ObjectId(request_id)})
        except:
            return None

    async def delete_request(self, request_id):
        from bson.objectid import ObjectId
        try:
            await self.col.delete_one({"_id": ObjectId(request_id)})
        except:
            pass

requests_db = RequestsDB(USER_DB_URI, DATABASE_NAME)
