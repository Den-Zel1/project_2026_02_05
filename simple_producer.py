# simple_producer.py
import json
import aio_pika
from pydantic import BaseModel

class TaskPayload(BaseModel):
    task: str
    data: dict

async def publish(channel, body: TaskPayload, queue: str):
    message = aio_pika.Message(
        body=json.dumps(body.model_dump()).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await channel.default_exchange.publish(message, routing_key=queue)