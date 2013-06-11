# -*- coding: utf-8 -*-

"""
    Copyright Hobbes / Bitcointalk 2013
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import csv

import dateutil, dateutil.parser
import copy

# todo:
#  Zeitzone
#  withdraw / deposit - wie händeln?
#  Gebühren schon abgezogen? vermutlich


taxFreeAfter1Year = True
taxRate = 0.26375


currency = "USD"
#currency = "EUR"



def remove_non_ascii(s): return "".join(i for i in s if ord(i)<128)

def clean_row(row):
    dRow = {}
    dRow = {"index":row[0], "date":row[1], "type":row[2], "info":row[3], "value":row[4], "balance":row[5]}
    dRow["info"] = dRow["info"].replace("฿", "B")
    dRow["info"] = dRow["info"].replace(" ", " ")  # remove weird non breaking space
    dRow["info"] = remove_non_ascii(dRow["info"])  # no more surprises

    if dRow["type"] == "out" and not " " in dRow["info"]:
        dRow["type"] = "withdraw"
    return dRow

class GoxParse(object):
    def __init__(self):
        self.fees = {}
        self.bought = {}
        self.sold = {}
        self.tax = {}
    def parse_info(self, s):
        if len(s.split(" ")) > 1:
            try:
                amount = float(s.split(" ")[3])
                price = float(s.split(" ")[6][1:])
            except (ValueError, IndexError) :  # z.B. coupon code
                return None, None
            return amount, price
        return None, None
    def buy(self, t, dRow):
        self.bought[t] = dRow
        amount, price = self.parse_info(dRow["info"])
        if amount:
            self.bought[t]["amount"] = amount
            self.bought[t]["price"] = price
            return price
    def sell(self, t, dRow):
        self.sold[t] = dRow
        amount, price = self.parse_info(dRow["info"])
        if amount:
            self.sold[t]["amount"] = amount
            self.sold[t]["price"] = price
            return price
        return None
    
    def parse_fiat(self, filename):

        # usd
        with open(filename, "rb") as f:
            cr = csv.reader(f, delimiter=",")
            self.headerFiat = cr.next()
            for row in cr:
                # raw output
                #print unicode(", ".join(row), encoding="utf-8")

                dRow = clean_row(row)
                
                t = dateutil.parser.parse(dRow["date"])

                if dRow["type"] == "spent":
                    self.buy(t, dRow)
                if dRow["type"] == "earned":
                    self.sell(t, dRow)
                if dRow["type"] == "fee":
                    if self.fees.has_key(t.year):
                        self.fees[t.year] += float(dRow["value"])
                    else:
                        self.fees[t.year] = float(dRow["value"])
                    
        print

    def parse_btc(self, filename):
        with open(filename, "rb") as f:
            cr = csv.reader(f, delimiter=",")
            self.headerBtc = cr.next()
            price = None
            for row in cr:
                # raw output
                #print unicode(", ".join(row), encoding="utf-8")
                
                dRow = clean_row(row)
                t = dateutil.parser.parse(dRow["date"])
                
                if dRow["type"] == "in":
                    price = self.buy(t, dRow)
                if dRow["type"] == "out":
                    price = self.sell(t, dRow)
                if dRow["type"] == "fee":
                    if self.fees.has_key(t.year):
                        self.fees[t.year] += float(dRow["value"]) * previousPrice
                    else:
                        self.fees[t.year] = float(dRow["value"]) * previousPrice
                
                if price:
                    previousPrice = price # falsch bei withdraw --> tatsaechlicher Preis muesste aus externer Quelle geholt werden
        print

    def process(self):
        bought = copy.copy(self.bought)
        sold = copy.copy(self.sold)
        
        self.taxSum = {}
        self.tax = {}
        self.profit = {}
        
        BK = sorted(bought.keys())

        SK = sorted(sold.keys())

        bi = 0
        si = 0
        while 1:
            #print sold[SK[si]]
            #print bought[BK[bi]]
            #print
            y = SK[si].year
            if not self.tax.has_key(y):
                self.tax[y] = []
                self.taxSum[y] = 0
                self.profit[y] = 0
            if sold[SK[si]]["amount"] < bought[BK[bi]]["amount"]:
                self.tax[y].append(sold[SK[si]])
                self.tax[y][-1]["age"] = SK[si] - BK[bi]
                self.tax[y][-1]["date"] = SK[si]
                self.tax[y][-1]["profit"] = sold[SK[si]]["amount"] * (sold[SK[si]]["price"] - bought[BK[bi]]["price"])
                self.profit[y] += self.tax[y][-1]["profit"]                
                bought[BK[bi]]["amount"] -= sold[SK[si]]["amount"]
                sold.pop(SK[si])
                si += 1
            elif sold[SK[si]]["amount"] >= bought[BK[bi]]["amount"]:
                self.tax[y].append(bought[BK[bi]])
                self.tax[y][-1]["age"] = SK[si] - BK[bi]
                self.tax[y][-1]["date"] = SK[si]                
                self.tax[y][-1]["profit"] = bought[BK[bi]]["amount"] * (sold[SK[si]]["price"] - bought[BK[bi]]["price"])
                self.profit[y] += self.tax[y][-1]["profit"]                
                sold[SK[si]]["amount"] -= bought[BK[bi]]["amount"]
                if sold[SK[si]]["amount"] == bought[BK[bi]]["amount"]:
                    sold.pop(SK[si])
                    si += 1
                bought.pop(BK[bi])
                bi += 1
            
            if si >= len(SK) or bi >= len(BK):
                break

        # sum up
        for ty in sorted(self.tax.keys()):
            for t in self.tax[ty]:
                if taxFreeAfter1Year and t["age"].days > 366:  #
                    continue
                
                print ty, t["profit"], t["age"].days
                self.taxSum[t["date"].year] += t["profit"] * taxRate
            print
        

    def run(self):
        self.parse_fiat("history_" + currency + ".csv")
        self.parse_fiat("history_" + currency + "_recent.csv")
                        
        self.parse_btc("history_btc.csv")
        self.parse_btc("history_btc_recent.csv")

        self.process()

        print

        for y in self.fees:
            print "year:", y
            print "fees %f %s" % (self.fees[y], currency)

            print "profit:", self.profit[y]
            print "tax:", self.taxSum[y]
            print
        


if __name__ == "__main__":
    gp = GoxParse()
    gp.run()
