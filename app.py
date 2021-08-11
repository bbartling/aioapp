from aiohttp import web
from datetime import datetime
import json
import pytz
import asyncio
import aiosqlite
import aiohttp_jinja2
import aiosqlite
import time
import sqlite3
from typing import Any, AsyncIterator, Dict
import jinja2
import aiohttp_jinja2
import os



routes = web.RouteTableDef()
tz = pytz.timezone('America/Chicago')



'''
FUNCTION TO VOLTTRON REST ENDPOINT
'''

def payload_condition_checker(data):
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    print("Current Time for Payload Check is ", current_time)
    # To Get the Week Number
    current_day = datetime.today().weekday()
    print("Current Weekday Number for Payload Check is ", current_day)

    for info in data:
        print(info)  
    between_time = info['starttime'] <= current_time <= info['endtime']
    disabled = info['Weekends'] == str(False) and info['Weekdays'] == str(False)
    weekday_rules = current_day in [0,1,2,3,4]
    weekend_rules = current_day in [5,6]
    if between_time and not disabled and weekday_rules or between_time and not disabled and weekend_rules:
        return True
    else:
        return False



'''
HOMEPAGE
'''
@routes.get('/')
@aiohttp_jinja2.template("index.html")
async def index_handler(request):
    #return web.FileResponse('load-roller-setpoint.html')
    return {}

'''
AFTER SETPOINTS ARE ENTERED WE GO HERE:
'''

@routes.post('/transform')
async def form_grabber(request: web.Request) -> web.Response:
    db = request.config_dict["DB"]
    post = await request.post()
    print(post)

    stamp = time.time()
    Date = datetime.fromtimestamp(stamp)    
    try:
        setpoint = int(post["setpoint"])
        print("setpoint is ", setpoint)
        weekends_weekdays_verify = ['Weekdays', 'Weekends']
        weekends_weekdays = all(key in post for key in weekends_weekdays_verify)
        print("Form data weekends and weekdays ", weekends_weekdays)
        weekdays_verify = ['Weekdays']
        weekdays = all(key in post for key in weekdays_verify)
        print("Form data weekdays only ", weekdays)
        weekends_verify = ['Weekends']
        weekends = all(key in post for key in weekends_verify)
        print("Form data weekends only ", weekends)

        # need to verify times & kW entered are good
        rules = [post['starttime'] < post['endtime'],
                setpoint > 40]

        if all(rules): # bad time's entered or kW entered too low
            print("Rules Success!")
            if weekends_weekdays: # If no dates, then its disabled
                info = f'Weekends and Weekdays Found'
                print(info)
                response_obj = { 'status' : 'success', 'info' : info }
                await db.execute(
                    "INSERT INTO posts (Date, starttime, endtime, Weekends, Weekdays, setpoint) VALUES(?, ?, ?, ?, ?, ?)",
                    [Date, post["starttime"], post["endtime"], post["Weekends"], post["Weekdays"], post["setpoint"]],
                )
                await db.commit()
                return web.json_response(response_obj)

            elif weekdays:
                info = f'Weekdays Found'
                print(info)
                response_obj = { 'status' : 'success', 'info' : info }
                await db.execute(
                    "INSERT INTO posts (Date, starttime, endtime, Weekends, Weekdays, setpoint) VALUES(?, ?, ?, ?, ?, ?)",
                    [Date, post["starttime"], post["endtime"], 0, 1, post["setpoint"]],
                )
                await db.commit()
                return web.json_response(response_obj)

            elif weekends:
                info = f'Weekends Found'
                print(info)
                response_obj = { 'status' : 'success', 'info' : info }
                await db.execute(
                    "INSERT INTO posts (Date, starttime, endtime, Weekends, Weekdays, setpoint) VALUES(?, ?, ?, ?, ?, ?)",
                    [Date, post["starttime"], post["endtime"], 1, 0, post["setpoint"]],
                )
                await db.commit()
                return web.json_response(response_obj)

            else:
                info = f'NO Weekdays or Weekends Found, event will be disabled'
                print(info)
                response_obj = { 'status' : 'success', 'info' : info }
                await db.execute(
                    "INSERT INTO posts (Date, starttime, endtime, Weekends, Weekdays, setpoint) VALUES(?, ?, ?, ?, ?, ?)",
                    [Date, post["starttime"], post["endtime"], 0, 0, post["setpoint"]],
                )
                await db.commit()              
                return web.json_response(response_obj)            

        else:
            err = f'Bad Times Entered, or kW Setpoint below 40 was entered'
            response_obj = { 'status' : 'failed', 'reason': err }
            ## return failed with a status code of 400 i.e. 'Bad Request'
            return web.Response(text=json.dumps(response_obj), status=400)


    except Exception as e:
        ## Bad path where name is not set
        response_obj = { 'status' : 'failed', 'reason': str(e) }
        ## return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

'''
THIS WILL DISPLAY LAST EVENT CONFIG
'''

@routes.get('/current-event-info')
async def get_current_event_info(request):
    container = []
    db = request.config_dict["DB"]
    async with db.execute("SELECT * FROM posts ORDER BY rowid DESC LIMIT 1;") as cursor:
        async for row in cursor:
            container.append(
                {
                    "Date": row["Date"],
                    "starttime": row["starttime"],
                    "endtime": row["endtime"],
                    "Weekends": row["Weekends"],
                    "Weekdays": row["Weekdays"],
                    "setpoint": row["setpoint"],
                }
            )

    response_obj = { 'status' : 'success', 'info' : container }
    return web.json_response(response_obj)

'''
SEE ALL CONFIGED EVENT HISTORIES
'''

@routes.get('/event-info-history')
async def get_all_event_info(request):
    container = []
    db = request.config_dict["DB"]
    async with db.execute("SELECT Date, starttime, endtime, Weekends, Weekdays, setpoint FROM posts") as cursor:
        async for row in cursor:
            container.append(
                {
                    "Date": row["Date"],
                    "starttime": row["starttime"],
                    "endtime": row["endtime"],
                    "Weekends": row["Weekends"],
                    "Weekdays": row["Weekdays"],
                    "setpoint": row["setpoint"],
                }
            )

    response_obj = { 'status' : 'success', 'info' : container }
    return web.json_response(response_obj)

'''
VOLTTRON HITS THIS REST ENDPOINT TO GET KW SETPOINT ONLY
'''

@routes.get('/event-payload')
async def get_event_payload(request):
    container = []
    db = request.config_dict["DB"]
    async with db.execute("SELECT * FROM posts ORDER BY rowid DESC LIMIT 1;") as cursor:
        async for row in cursor:
            container.append(
                {
                    "starttime": row["starttime"],
                    "endtime": row["endtime"],
                    "Weekends": row["Weekends"],
                    "Weekdays": row["Weekdays"],
                    "setpoint": row["setpoint"],
                }
            )  

    for info in container:
        print(info)
    setpoint = int(info["setpoint"])

    if payload_condition_checker(container):
        print("payload_condition_checker TRUE")
        response_obj = { 'status' : 'success', 'info' : setpoint }
        return web.json_response(response_obj)

    else:
        print("payload_condition_checker FALSE")
        response_obj = { 'status' : 'success', 'info' : 0 }
        return web.json_response(response_obj)


'''
APP CONFIG BELOW
'''

async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes([web.get("/", index_handler)])
    app.add_routes([web.post("/transform", form_grabber)])
    app.add_routes([web.get("/event-info-history", get_all_event_info)])
    app.add_routes([web.get("/current-event-info", get_current_event_info)])
    app.add_routes([web.get("/event-payload", get_event_payload)])
    app.cleanup_ctx.append(init_db)
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader("templates"))

    return app


                

def try_make_db() -> None:
    my_path = 'form_data.db'
    with sqlite3.connect(my_path) as conn:
        cur = conn.cursor()
        print("Trying to connect to the db!")
        try:
            cur.execute("SELECT 1 FROM posts LIMIT 1;")
            cur.close()
            print("Good enough DB should be Ok")
        except Exception as e:
            print("Table 'posts' does not exist")
            cur.execute(
                """CREATE TABLE posts (
                Date TEXT PRIMARY KEY,
                starttime TEXT,
                endtime TEXT,
                Weekends NUMBER,
                Weekdays NUMBER,
                setpoint NUMBER)
            """
            )
            print("DB TABLE CREATED")
            conn.commit()

async def init_db(app: web.Application) -> AsyncIterator[None]:
    sqlite_db = 'form_data.db'
    db = await aiosqlite.connect(sqlite_db)
    db.row_factory = aiosqlite.Row
    app["DB"] = db
    yield
    await db.close()

try_make_db()


web.run_app(init_app()  , host='0.0.0.0', port=8080)
