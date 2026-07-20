import pymongo
import json

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

with open("configs/config_mongo.json", "r", encoding="utf-8") as f:
    mongo_config = json.load(f)

mongo_url = mongo_config.get("mongoURL")
bot_id = config.get("botID")
database_name = mongo_config.get("databaseName", "sync_bots")

client = pymongo.MongoClient(mongo_url)
database = client[database_name]
collection = database[bot_id]