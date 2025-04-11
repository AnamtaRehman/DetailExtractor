# -*- coding: utf-8 -*-
"""Another copy of finalMain

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1rjuVHRAsAZcVUAeO9v8L9uBTLYSuQu43
"""

from groq import Groq
import base64
import torch
import re
import os
import base64
import io
import sqlite3
import pytz
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import pandas as pd
import uvicorn
from PIL import Image
import nest_asyncio
from fastapi.middleware.cors import CORSMiddleware
from pyngrok import ngrok
import json
from datetime import datetime
from typing import List


#API KEY
client = Groq(api_key='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')

"""
This FastAPI web application processes product and freshness details extracted from images. It includes:

1. SQLite database management to store product details (name, MRP, expiry date, etc.) and freshness information (produce type, freshness index, and expected lifespan).
2. API endpoints to fetch product and freshness data from the databases.
3. Functions to extract and save product information and freshness details from images using AI models.
4. Error handling to ensure missing details are marked as "NA".
5. User-friendly interface for easy image uploads and viewing product data.
6. Clear sections to display product details (e.g., name, MRP, expiry date) and freshness information.
7. Option to download or save processed data for inventory management.
"""


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

IMAGE_FOLDER = os.path.join(os.getcwd(), 'images')
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)


# SQLite database setup for product details
def connect_to_db(db_name="product_details.db"):
    return sqlite3.connect(db_name)

# SQLite database setup for freshness details
def connect_to_freshness_db(db_name="freshness_details.db"):
    return sqlite3.connect(db_name)

# Creating product_details table
def create_table(conn):
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS product_details (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT,
                        mrp REAL,
                        net_content TEXT,
                        expiry_date TEXT,
                        quantity INTEGER,
                        timestamp TEXT,
                        expired TEXT,
                        expected_life TEXT)''')
    conn.commit()

# Creating freshness_details table
def create_freshness_table(conn):
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS freshness_details (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        Timestamp TEXT,
                        Produce TEXT,
                        Freshness INTEGER,
                        Expected_Life_Span INTEGER)''')
    conn.commit()

# Saving extracted product details in the Database
def save_multiple_to_database(conn, products):
    cursor = conn.cursor()
    for product in products:
        cursor.execute('''INSERT INTO product_details (
                            product_name, mrp, net_content, expiry_date, quantity, timestamp, expired, expected_life)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (product["Product Name"], product["MRP"], product["Net Content"],
                        product["Expiry Date"], product["Quantity"], product["Timestamp"],
                        product["Expired"], product["ExpectedLife"]))
    conn.commit()

# Saving freshness details in the Database
def save_multiple_to_freshness_database(conn, produce_details):
    cursor = conn.cursor()
    for produce in produce_details:
        cursor.execute('''INSERT INTO freshness_details (
                           Timestamp, Produce, Freshness, Expected_Life_Span)
                          VALUES (?, ?, ?, ?)''',
                       (produce["Timestamp"], produce["Produce"], produce["Freshness"],
                        produce["Expected_Life_Span"]))
    conn.commit()



# Function to extract the details
def extract_product_details_from_image(image_path):
    # Convert image to base64
    with Image.open(image_path) as img:
        # Convert image to RGB if it's not
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Create a bytes buffer for the JPEG image
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    try:
        # Make the API call
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Find the following details for each product in the image:
1. Product Name (if missing, return "NA").
2. Maximum Retail Price (MRP) (if missing, return "NA").
3. Expiry Date: Extract dates **only if they are explicitly labeled** with "EXP," "Expiry," or similar. Ensure the label is directly associated with the date, and reformat the date to **DD/MM/YY** or **MM/YY**. If no such label is present, return "NA."
4. Net Content (if missing, return "NA").

Rules for Date Extraction:
- Ignore any date that does not have a label such as "EXP," "Expiry," or equivalent before the date.
- Do not infer unlabeled or ambiguous dates as expiry dates.

For each product, also return the quantity (number of occurrences of that product in the image).

Return the data in the following JSON format ONLY:
```json
{
    "products": [
        {"Product Name": "<value>", "MRP": "<value (only real numbers)>", "Expiry Date": "<value>", "Net Content": "<value>", "Quantity": <count>}
    ]
}
"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model="llama-3.2-90b-vision-preview",
        )

        # Extract the response content
        output = chat_completion.choices[0].message.content
        print(output)
        # Clean up the response and parse JSON
        json_pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(json_pattern, output, re.DOTALL)

        if match:
            json_text = match.group(1)  # Extract JSON block
        else:
            json_text = output.strip()  # Fallback to plain text if no match

        # Parse JSON
        try:
            result = json.loads(json_text)
        except json.JSONDecodeError:
            # Return default structure if JSON parsing fails
            result = {
                "products": [{
                    "Product Name": "NA",
                    "MRP": "NA",
                    "Expiry Date": "NA",
                    "Net Content": "NA",
                    "Quantity": 0
                }]
            }

        return result

    except Exception as e:
        # Return default structure if API call fails
        return {
            "products": [{
                "Product Name": "NA",
                "MRP": "NA",
                "Expiry Date": "NA",
                "Net Content": "NA",
                "Quantity": 0
            }]
        }


# Function to extract the freshness details
def extract_freshness_details_for_multiple(image_path):
    # Convert image to base64
    with Image.open(image_path) as img:
        # Convert image to RGB if it's not
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Create a bytes buffer for the JPEG image
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    try:
        # Make the API call
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """
detect the fresh produce objects in image, Each object must be treated as a separate entity. For every item, provide:

1. Produce Name
2. Freshness Index (0-10 scale as defined below):
  0-1.9: Unsellable - Completely spoiled, showing mold, decay, or severe damage.
  2.0-3.9: Poor - Major quality issues like bruising, wilting, or discoloration.
  4.0-5.9: Fair - Some deterioration with minor blemishes or wilting.
  6.0-7.9: Good - Mostly fresh with minimal defects, suitable for sale.

3. Expected Life Span (in days).

Important:
Detect the number of items in image and the resultant json should strictly have the same count of items.
Return the output in the following JSON format ONLY:
Also provide the positions of each item
```json
{
    "produce_details": [
        {"Produce": "<name>", "Freshness": "<index>", "Expected_Life_Span": "<days>"},
        ...
    ]
}"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model="llama-3.2-90b-vision-preview",
        )

        # Extract the response content
        output = chat_completion.choices[0].message.content
        print(output)

        # Clean up the response and parse JSON using regex
        json_pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(json_pattern, output, re.DOTALL)

        if match:
            json_text = match.group(1)  # Extract JSON block
        else:
            json_text = output.strip()  # Fallback to plain text if no match

        try:
            print("JSON text is = ")
            print(json_text)
            result = json.loads(json_text)
            print("Result is = " + str(result))
        except json.JSONDecodeError:
            # Return default structure if JSON parsing fails
            result = {
                "produce_details": [
                    {"Produce": "NA", "Freshness": "NA", "Expected_Life_Span": "NA"}
                ]
            }

        return result

    except Exception as e:
        # Return default structure if API call fails
        return {
            "produce_details": [
                {"Produce": "NA", "Freshness": "NA", "Expected_Life_Span": "NA"}
            ]
        }
#Function to incorporate various date formats
def parse_expiry_date(expiry_date_str: str) -> datetime:
    expiry_date_str = expiry_date_str.strip().upper()


    date_formats = [
    # Basic formats
    "%m/%Y",        # MM/YYYY
    "%d/%m/%Y",     # DD/MM/YYYY
    "%d/%m/%y",     # DD/MM/YY
    "%m/%d/%Y",     # MM/DD/YYYY
    "%m/%d/%y",     # MM/DD/YY
    "%Y/%m/%d",     # YYYY/MM/DD
    "%Y/%d/%m",     # YYYY/DD/MM
    "%d-%m-%Y",     # DD-MM-YYYY
    "%m-%d-%Y",     # MM-DD-YYYY
    "%Y-%m-%d",     # YYYY-MM-DD
    "%Y-%d-%m",     # YYYY-DD-MM
    "%b %Y",        # Mon YYYY
    "%B %Y",        # Month YYYY
    "%Y %b",        # YYYY Mon
    "%Y %B",        # YYYY Month

    # Formats with time
    "%d/%m/%Y %H:%M:%S",  # DD/MM/YYYY HH:MM:SS
    "%d/%m/%y %H:%M:%S",  # DD/MM/YY HH:MM:SS
    "%Y-%m-%dT%H:%M:%S",  # ISO 8601 (YYYY-MM-DDTHH:MM:SS)
    "%d/%m/%Y %H:%M",     # DD/MM/YYYY HH:MM
    "%d-%m-%Y %H:%M:%S",  # DD-MM-YYYY HH:MM:SS
    "%Y-%m-%d %H:%M:%S",  # YYYY-MM-DD HH:MM:SS

    # Month and day with names
    "%d/%b/%Y",     # DD/Mon/YYYY (e.g., 05/Sep/2023)
    "%d/%b/%y",     # DD/Mon/YY (e.g., 05/Sep/23)
    "%d/%B/%Y",     # DD/Month/YYYY (e.g., 05/September/2023)
    "%d-%b-%Y",     # DD-Mon-YYYY (e.g., 05-Sep-2023)
    "%d-%B-%Y",     # DD-Month-YYYY (e.g., 05-September-2023)
    "%b-%Y",        # Mon-YYYY (e.g., Sep-2023)
    "%B-%Y",        # Month-YYYY (e.g., September-2023)

    # Full-text formats
    "%A, %d %B %Y",       # Weekday, DD Month YYYY
    "%a, %d %b %Y",       # Abbreviated weekday, DD Mon YYYY
    "%A, %d/%B/%Y",       # Weekday, DD/Month/YYYY
    "%a, %d-%b-%Y",       # Abbreviated weekday, DD-Mon-YYYY

    # Julian formats
    "%j/%Y",              # DDD/YYYY (Julian day/year)
    "%Y/%j",              # YYYY/DDD
    "%j-%Y",              # DDD-YYYY

    # Dot-delimited formats
    "%d.%m.%Y",           # DD.MM.YYYY
    "%m.%d.%Y",           # MM.DD.YYYY
    "%Y.%m.%d",           # YYYY.MM.DD
    "%d.%m.%y",           # DD.MM.YY
    "%m.%d.%y",           # MM.DD.YY
    "%y.%m.%d",           # YY.MM.DD
    "%d.%b.%Y",           # DD.Mon.YYYY
    "%d.%B.%Y",           # DD.Month.YYYY
    "%b.%d.%Y",           # Mon.DD.YYYY
    "%B.%d.%Y",           # Month.DD.YYYY
    "%b.%Y",              # Mon.YYYY
    "%B.%Y",              # Month.YYYY
    "%Y.%b.%d",           # YYYY.Mon.DD
    "%Y.%B.%d",           # YYYY.Month.DD

    # Compact and ISO-like dot formats
    "%Y.%m.%d.%H.%M.%S",  # YYYY.MM.DD.HH.MM.SS
    "%d.%m.%Y.%H.%M.%S",  # DD.MM.YYYY.HH.MM.SS
    "%d.%m.%Y.%H.%M",     # DD.MM.YYYY.HH.MM
    "%Y.%j",              # YYYY.DDD
    "%j.%Y",              # DDD.YYYY

    # Variants with apostrophes and compact formats
    "%d/%b/'%y",          # DD/Mon/'YY (e.g., 05/Dec/'23)
    "%d/%B/'%y",          # DD/Month/'YY (e.g., 05/December/'23)
    "%b.'%y",             # Mon.'YY (e.g., Dec.'23)
    "%B.'%y",             # Month.'YY (e.g., December.'23)
    "%Y%m%d%H%M%S",       # Compact: YYYYMMDDHHMMSS
    "%d%m%y%H%M",         # Compact: DDMMYYHHMM
    "%d/%b/%Y %H:%M:%S",  # DD/Mon/YYYY HH:MM:SS
    "%Y-%m-%dT%H:%M:%SZ", # ISO 8601 with timezone (e.g., 2024-12-10T14:00:00Z)

    # Week-based formats
    "%Y-W%W-%w",          # ISO Week-Date (e.g., 2024-W50-1)
    "%Y.W%W.%w",          # Week-Based with dots (e.g., 2024.W50.1)

    # Additional requested formats
    "%m.%d",              # MM.DD (e.g., 01.26)
    "%b.%d",              # Mon.DD (e.g., JAN.26)
    "%B.%d",              # Month.DD (e.g., January.26)
    "%b/%Y",              # Mon/YYYY (e.g., JAN/2026)
    "%b/%y",              # Mon/YY (e.g., JAN/26)
    "%B/%Y",              # Month/YYYY (e.g., January/2026)
    "%B/%y",              # Month/YY (e.g., January/26)
    "%b/%d",              # Mon/DD (e.g., JAN/26)
    "%B/%d",              # Month/DD (e.g., January/26)
    "%b. %Y",
]


    for fmt in date_formats:
        try:

            if fmt in ["%m/%Y", "%b %Y", "%Y %b", "%b-%Y", "%Y-%b"]:
                expiry_date_obj = datetime.strptime(f"01/{expiry_date_str}", "%d/%m/%Y")
            elif fmt in ["%d/%b/%Y %H:%M:%S", "%d/%b/%Y %H:%M", "%d/%m/%Y %H:%M:%S"]:

                expiry_date_obj = datetime.strptime(expiry_date_str.split()[0], fmt.split()[0])
            else:
                expiry_date_obj = datetime.strptime(expiry_date_str, fmt)
            return expiry_date_obj
        except ValueError:
            continue


    return None

@app.get("/get-database")
async def get_database():
    conn = connect_to_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM product_details")
    rows = cursor.fetchall()
    conn.close()

    current_date = datetime.now()
    products = []

    for row in rows:
        product_name = row[1]
        expiry_date = row[4]
        quantity = row[5]
        mrp = row[2]
        net_content = row[3]
        timestamp = row[6]
        expired_status = row[7]
        expected_life = row[8]

        products.append({
            "SlNo": len(products) + 1,
            "Product": product_name,
            "Timestamp": timestamp,
            "NetContent": net_content,
            "MRP": mrp,
            "ExpiryDate": expiry_date,
            "Quantity": quantity,
            "Expired": expired_status,
            "ExpectedLife": expected_life
        })

    return {"products": products}

@app.get("/get-freshdetails-database")
async def get_details_database():
    conn = connect_to_freshness_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM freshness_details")
    rows = cursor.fetchall()
    conn.close()

    produces = []

    for row in rows:

        timestamp = row[1]
        produce = row[2]
        freshness = row[3]
        expected_life = row[4]

        produces.append({
            "SlNo": len(produces) + 1,
            "Timestamp": timestamp,
            "Produce": produce,
            "Freshness": freshness,
            "Expected_Life_Span": expected_life
        })

    return {"produces": produces}

@app.post("/detailsextract-details")
async def extract_details():
    image_path = os.path.join(IMAGE_FOLDER, "captured_image.jpg")

    if os.path.exists(image_path):

        products = extract_product_details_from_image(image_path)["products"]

        current_date = datetime.now(pytz.timezone("Asia/Kolkata"))
        for product in products:
            product["Timestamp"] = current_date.isoformat()


            if product["Expiry Date"] != "NA":
                expiry_date_obj = parse_expiry_date(product["Expiry Date"])

                if expiry_date_obj is not None:

                    if expiry_date_obj.tzinfo is None:
                        expiry_date_obj = pytz.timezone("Asia/Kolkata").localize(expiry_date_obj)


                    expired_status = "Yes" if expiry_date_obj < current_date else "No"


                    months_diff = (expiry_date_obj.year - current_date.year) * 12 + expiry_date_obj.month - current_date.month
                    expected_life = f"{months_diff} month(s)" if months_diff > 0 else "NA"
                else:
                    expired_status, expected_life = "Invalid Date", "NA"
            else:
                expired_status, expected_life = "NA", "NA"


            product["Expired"] = expired_status
            product["ExpectedLife"] = expected_life


        conn = connect_to_db()
        create_table(conn)
        save_multiple_to_database(conn, products)
        conn.close()
        print(products)
        return {"products": products}

    raise HTTPException(status_code=404, detail="Image not found")

@app.post("/extract-details")
async def freshnessextract_details():
    image_path = os.path.join(IMAGE_FOLDER, "captured_image.jpg")

    if os.path.exists(image_path):
        # Get the data from the extractor
        produce_details = extract_freshness_details_for_multiple(image_path)

        current_date = datetime.now(pytz.timezone("Asia/Kolkata"))

        # Add timestamp to each produce detail
        for produce in produce_details["produce_details"]:
            produce["Timestamp"] = current_date.isoformat()

        # Save to database
        conn = connect_to_freshness_db()
        create_freshness_table(conn)
        save_multiple_to_freshness_database(conn, produce_details["produce_details"])
        conn.close()

        # Return the produce_details directly
        return produce_details  # Don't wrap it again

    raise HTTPException(status_code=404, detail="Image not found")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    with open("templates/details.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/freshnessIndexPage", response_class=HTMLResponse)
async def freshness_index_page(request: Request):
    with open("templates/freshness.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image_path = os.path.join(IMAGE_FOLDER, "captured_image.jpg")

        with open(image_path, "wb") as f:
            f.write(contents)

        return {"filename": file.filename, "status": "uploaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/detailsdownload-csv")
async def download_csv():
    conn = connect_to_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT product_name, net_content, mrp, expiry_date, quantity, timestamp, expired, expected_life  FROM product_details")
        rows = cursor.fetchall()
        conn.close()


        if not rows:
            raise HTTPException(status_code=404, detail="No product details found in the database.")


        data = {
            "Product Name": [row[0] for row in rows],
            "Net Content": [row[1] for row in rows],
            "MRP": [row[2] for row in rows],
            "Expiry Date": [row[3] for row in rows],
            "Quantity": [row[4] for row in rows],
            "Timestamp": [row[5] for row in rows],
            "Expired": [row[6] for row in rows],
            "Expected Life": [row[7] for row in rows],

        }
        df = pd.DataFrame(data)


        stream = io.StringIO()
        df.to_csv(stream, index=False)
        stream.seek(0)


        return StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=product_details.csv"}
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")


@app.get("/freshnessdownload-csv")
async def freshness_download_csv():
    conn = connect_to_freshness_db()
    cursor = conn.cursor()

    try:

        cursor.execute("SELECT Timestamp, Produce, Freshness, Expected_Life_Span  FROM freshness_details")
        rows = cursor.fetchall()
        conn.close()


        if not rows:
            raise HTTPException(status_code=404, detail="No freshness details found in the database.")


        data = {
            "Timestamp": [row[0] for row in rows],
            "Produce": [row[1] for row in rows],
            "Freshness": [row[2] for row in rows],
            "Expected_Life_Span": [row[3] for row in rows],

        }
        df = pd.DataFrame(data)


        stream = io.StringIO()
        df.to_csv(stream, index=False)
        stream.seek(0)  # Reset the stream pointer


        return StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=freshness_details.csv"}
        )
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")


# Start ngrok tunnel
public_url = ngrok.connect(8000)
print(f" * ngrok tunnel URL: {public_url}")

nest_asyncio.apply()
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)