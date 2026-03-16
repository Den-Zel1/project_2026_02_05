# simple_producer.py
import json
import aio_pika
from pydantic import BaseModel


async def publish(channel, body: dict, queue: str):
    message = aio_pika.Message(
        body=json.dumps(body).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await channel.default_exchange.publish(message, routing_key=queue)