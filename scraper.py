import scraperwiki
import urllib, urlparse
import lxml.html, lxml.etree
import re
import tempfile, zipfile

urlarch = "http://www.un.org/en/peacekeeping/resources/statistics/contributors_archive.shtml"
urlstats = "http://www.un.org/en/peacekeeping/resources/statistics/contributors.shtml"

#scraperwiki.sqlite.save_var("mostrecentmonth", "2011-11")

def Main():
    #/en/peacekeeping/contributors/2002/countrymission.zip

    # archived years (in zip files)
    if False:
        #ExtractYear('2008', "http://www.un.org/en/peacekeeping/contributors/2008/countrymission.zip")
        for year, lurl in MakeLinks('countrymission'):
            if year >= '2003':
                #print year, lurl
                ExtractYear(year, lurl)

    # the month pdfs on front page
    recentmonth = scraperwiki.sqlite.get_var("mostrecentmonth", "2011-11")
    newrm = [ ]
    for year, lnk, nz in ExtractRecent():
        #print year, lnk, nz
        pdfbin = urllib.urlopen(lnk).read()
        dnz, nrecords = ExtractPdf(year, nz, pdfbin, lnk)
        if dnz > recentmonth:
            newrm.append((dnz, nrecords))
    if newrm:
        newrecentmonth = max(rm[0]  for rm in newrm)
        print "EMAILSUBJECT: UN peacekeeping statistics for %s" % newrecentmonth 
        print "Dear friend,\nThere are %d new records in the database for\n https://scraperwiki.com/scrapers/un_peacekeeping_statistics/\n" % sum(rm[1]  for rm in newrm)
        print "after month %s to month %s\n" % (recentmonth, newrecentmonth)
        scraperwiki.sqlite.save_var("mostrecentmonth", newrecentmonth)
        


def ExtractRecent():
    html = urllib.urlopen(urlstats).read()
    root = lxml.html.fromstring(html)
    lnks = [ ]
    for h4 in root.cssselect("div#text h4"):
        for a in h4.getnext().cssselect("a"):
            if a.text == "Country contributions detailed by mission":
                lnk = urlparse.urljoin(urlstats, a.attrib.get("href"))
                mlnk = re.search("contributors/(\d\d\d\d)/(.*?_3.pdf)", lnk)
                assert mlnk, lnk
                lnks.append((mlnk.group(1), lnk, mlnk.group(2)))
    return lnks


def MakeLinks(typ):
    html = urllib.urlopen(urlarch).read()
    root = lxml.html.fromstring(html)
    res = [ ]
    for h3 in root.cssselect("div#text h3"):
        #print lxml.html.tostring(h3)
        ul = h3.getnext()
        for a in ul.cssselect("li a"):
            lurl = urlparse.urljoin(urlarch, a.attrib.get("href"))
            murl = re.search("contributors/(\d+)/(.*?).zip", lurl)
            if murl.group(2) == typ:
                res.append((murl.group(1), lurl))
    return res


def text_content(text):
    res = [ text.text or '' ]
    for r in text:
        res.append(r.text or '')
        res.append(r.tail or '')
    return "".join(res)

Ldescs = ["Contingent Troop", "Experts on Mission", "Formed Police Units", "Individual Police", 
          'Military Observer', 'Troop', 'Police', 'Civilian Police' ]

def parsemissionblock(rtblocks, data):
    descs = [ r  for r in rtblocks  if r.text and 380 <= int(r.attrib.get("left")) <=470 ]
    lndata = [ ]
    xx = "\n".join(lxml.etree.tostring(r)  for r in rtblocks)
    for d in descs:
        top = int(d.attrib.get("top"))
        drow = [ (int(r.attrib.get("left")), text_content(r))  for r in rtblocks  \
                    if r.text and top-2<=int(r.attrib.get("top"))<=top+2 ]
        drow.sort()
        np = [ int(lnp[1].replace(",", ""))  for lnp in drow[1:] ]
        desc = drow[0][1]
        if desc not in Ldescs:
            print "Unknown job description", desc
            print xx
            print data
            print drow
            assert False, desc
        if len(drow) == 2:
            assert data["year"] <= "2009" or data["nz"] in ['may12_3.pdf']
            ndata = { "desc":desc, "people":np[0] }
        elif len(drow) == 4:
            ndata = { "desc":desc, "men":np[0], "women":np[1], "people":np[2] }
        elif len(drow) == 1:
            assert data["nz"] in ['jul11_3.pdf', 'dec11_3.pdf', 'jun11_3.pdf', 'oct_3.pdf', 'may12_3.pdf'], (xx, data)
            ndata = None
        else:
            assert False, xx
        if ndata:
            ndata.update(data)
            lndata.append(ndata)
    return lndata

m3 = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

def ExtractYear(year, lurl):
    t = tempfile.NamedTemporaryFile(suffix=".zip")
    t.write(urllib.urlopen(lurl).read())
    t.seek(0)
    z = zipfile.ZipFile(t.name)
    for nz in z.namelist():
        pdfbin = z.read(nz)
        ExtractPdf(year, nz, pdfbin, lurl)


def ExtractPdf(year, nz, pdfbin, lurl):
    mnz = re.match("(...).*?(?:\d\d)?(\d\d)?_3.pdf", nz)
    assert mnz, nz
    assert mnz.group(1).lower() in m3, nz
    dnz = "%d-%02d" % (mnz.group(2) and int(mnz.group(2))+2000 or int(year), m3.index(mnz.group(1).lower())+1)
    #print "date", dnz
    root = lxml.etree.fromstring(scraperwiki.pdftoxml(pdfbin))
    currentcountry = None
    currentmission = None
    ldata = [ ]
    data = None
    for page in list(root):
        rtblocks = [ ]
        #print lxml.etree.tostring(page)
        for text in page:
            if text.tag != "text":
                continue

            if 130 <= int(text.attrib.get("left")) <= 140:
                #print lxml.etree.tostring(text)
                currentmission = None
                currentcountry = text_content(text).strip()
            if 276 <= int(text.attrib.get("left")) <= 280:
                if rtblocks and data:
                    lndata = parsemissionblock(rtblocks, data)
                    ldata.extend(lndata)
                currentmission = text_content(text).strip()
                data = {"link":lurl, "nz":nz, "month":dnz, "country":currentcountry, "mission":currentmission, "year":year}
                rtblocks = [ ]
            if int(text.attrib.get("left")) > 350:
                rtblocks.append(text)

        if rtblocks and data:
            lndata = parsemissionblock(rtblocks, data)
            ldata.extend(lndata)
    scraperwiki.sqlite.save(["month", "country", "mission", "desc"], ldata)
    return dnz, len(ldata)

Main()






