import asyncio
import logging
import websockets
from datetime import datetime

from ocpp.routing import on
from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call_result
from ocpp.v201.enums import RegistrationStatusType

logging.basicConfig(level=logging.INFO)

from aiohttp import web
import socketio
import asyncio

from concurrent.futures import ProcessPoolExecutor

queue = asyncio.Queue()  # create queue object
sio = socketio.AsyncServer(engineio_logger=True, cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

class ChargePoint(cp):
    @on('BootNotification')
    async def on_boot_notification(self, charging_station, reason, **kwargs):
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatusType.accepted
        )


async def on_connect(websocket, path):
    """ For every new charge point that connects, create a ChargePoint
    instance and start listening for messages.
    """
    try:
        requested_protocols = websocket.request_headers[
            'Sec-WebSocket-Protocol']
    except KeyError:
        logging.info("Client hasn't requested any Subprotocol. "
                 "Closing Connection")
        return await websocket.close()

    if websocket.subprotocol:
        logging.info("Protocols Matched: %s", websocket.subprotocol)
    else:
        # In the websockets lib if no subprotocols are supported by the
        # client and the server, it proceeds without a subprotocol,
        # so we have to manually close the connection.
        logging.warning('Protocols Mismatched | Expected Subprotocols: %s,'
                        ' but client supports  %s | Closing connection',
                        websocket.available_subprotocols,
                        requested_protocols)
        return await websocket.close()

    charge_point_id = path.strip('/')
    cp = ChargePoint(charge_point_id, websocket)

    await cp.start()


async def main():
    server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp2.0.1']
    )
    logging.info("WebSocket Server Started")
    await server.wait_closed()

async def handle_index(request):
    # sio.emit('ask', 'some data')
    response = await queue.get()  # block until there is something in the queue
    return web.Response(response, content_type='text/plain')


@sio.on('connect', namespace='/chat')
def connect(sid, environ):
    print("connect ", sid)

@sio.on('answer', namespace='/chat')
async def answer(sid, data):
    await queue.put(data)  # push the response data to the queue

@sio.on('disconnect', namespace='/chat')
def disconnect(sid):
    print('disconnect ', sid)

app.add_routes([web.get('/', handle_index)])

def do_websocket():
    asyncio.run(main())
    
def do_socketio():
    web.run_app(app)
    
if __name__ == '__main__':
    
    executor = ProcessPoolExecutor(2)
    loop = asyncio.new_event_loop()
    boo = loop.run_in_executor(executor, do_websocket)
    baa = loop.run_in_executor(executor, do_socketio)

    loop.run_forever()