'''
Python3

Example barcode scanner for electronic component suppliers (digikey, mouser, LCSC)
https://github.com/maholli/getparts
M.Holliday
'''

from pyzbar import pyzbar
from pylibdmtx import pylibdmtx
import time
import cv2, codecs
import numpy as np
import getparts
import os.path 
from os import path
import winsound
import click
from inventree.api import InvenTreeAPI
import logging
import coloredlogs
from inventree.part import Part
from inventree.stock import StockLocation
from inventree.stock import StockItem
from inventree.company import SupplierPart
from inventree.stock import StockItem

coloredlogs.install(level=logging.DEBUG)

app_credentials= {
    'code': 'AAA',
    'client_id': "BBB",
    'client_secret': "CCC",
    'mouser_key': "DDD"
}

inventree = InvenTreeAPI('http://spasys-infra.uni.lux:8123/', token="f1481a3a24b28fca486a8c839ed4cf62453d148f")

# Specify location
LOCATION = "Box DAA"
locations = StockLocation.list(inventree)
location = [l for l in locations if l.name == LOCATION][0]
logging.debug("Found location: {}".format(location))

# initialize barcode_api with our API credentials
api = getparts.API(app_credentials,debug=False)
state='Searching'
states={
    'Searching':(0,0,255),
    'Found':(0,255,0),
    'Duplicate':(0,165,255),
}

# File to save barcodes
barcodefile='barcodes.txt'
found = set()
poly=np.array([[[0,0],[0,0],[0,0],[0,0]]],np.int32)

# initialize the video stream and allow the camera sensor to warm up
print("Starting video stream...")
vs=cv2.VideoCapture(0)
if vs is None or not vs.isOpened():
    raise TypeError('Error starting video stream\n\n')

while True:
    code=False
    # read frame from webcam
    _,frame2 = vs.read()
    # check for a data matrix barcode
    barcodes = pylibdmtx.decode(frame2,timeout=10)
    if barcodes:
        code=True
    # if no data matrix, check for any other barcodes
    else:
        barcodes=pyzbar.decode(frame2)
        if barcodes:
            code=True
    if code:
        for item in barcodes:
            barcodeData = item.data
            # find and draw barcode outline
            try:
                pts=[]
                [pts.append([i.x,i.y]) for i in item.polygon]
                poly=np.array([pts],np.int32)
                cv2.polylines(frame2, [poly], True, (0,0,255),2)
            except AttributeError:
                # data matrix
                (x, y, w, h) = item.rect
                cv2.rectangle(frame2,(x,y),(x+w, y+h),(0,0,255),2)
            # if we haven't seen this barcode this session, add it to our list
            if barcodeData not in found:
                state='Found'
                found.add(barcodeData)
                logging.info("Detected barcode data!")
                winsound.Beep(440*2, 100)
                # query the barcode_api.py for barcode
                result = api.search(item,product_info=False)
                winsound.Beep(440*3, 100) 
                with codecs.open(barcodefile,'a', encoding='latin-1') as file:
                    file.write('{}\n'.format(codecs.decode(barcodeData,'latin-1')))
                    file.flush()

                string = "Insert component into Inventree stock?"

                if click.confirm(string, default=False):
                    logging.debug("inserting....")

                    # Try to find part in the database
                    #
                    #
                    #
                    # {
                    #    "CountryOfOrigin": "PH",
                    #    "DigiKeyPartNumber": "497-19774-ND",
                    #    "InvoiceId": 87714396,
                    #    "LotCode": null,
                    #    "ManufacturerName": "STMICROELECTRONICS",
                    #    "ManufacturerPartNumber": "STM32G031F6P6",
                    #    "ProductDescription": "IC MCU 32BIT 32KB FLASH 20TSSOP",
                    #    "PurchaseOrder": "",
                    #    "Quantity": 10,
                    #    "SalesorderId": 74465247
                    # }

                    response = result.response

                    parts = Part.list(inventree)
                    parts = [p for p in parts if p.name == response["ManufacturerPartNumber"]]

                    if len(parts) <= 0:
                        logging.info("Found no part, creating new")
                        
                        part = Part.create(inventree, {
                            'name': response["ManufacturerPartNumber"],
                            'description': response["ProductDescription"],
                            'category': 1,
                            'active': True,
                            'virtual': False,
                            ## Note - You do not have to fill out *all* fields
                        })

                        logging.info("Created new Part with PK {}".format(part.pk))

                        supplierpart = SupplierPart.create(inventree, { 'part': part.pk, 'supplier': 1, 'SKU': response["DigiKeyPartNumber"] })
                        logging.info("Created new Supplier/Part for Digikey with PK {}".format(supplierpart.pk))
                    else:
                        part = parts[0]
                        logging.info("Found part {} with PK {}".format(part.name, part.pk))

                    stock = StockItem.create(inventree, { 'part': part.pk, 'quantity': response["Quantity"], 'location': location.pk })
                    logging.info("Stored new stock entry with {} items with PK {}".format(stock.quantity, stock.pk))
                
            else:
                state='Duplicate'
                logging.warning("Found duplicate barcode")
        code=False
    else:
        state='Searching'
    # update the video stream window
    cv2.putText(frame2,str(state),(10,10),cv2.FONT_HERSHEY_SIMPLEX,0.5,states[state],2,cv2.LINE_AA)
    cv2.imshow("Barcode Scanner", frame2)
    key = cv2.waitKey(1) & 0xFF

    # if the `q` key was pressed, break from the loop
    if key == ord("q"):
        break

print("Cleaning up...")
cv2.destroyAllWindows()
