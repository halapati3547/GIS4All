"""Code tables. LU24 labels come from the SCAG layer metadata (not assumed); zoning is ASSUMPTION."""

# --- LU24: read from the layer's own metadata "Value Description" (no coded-value domain exists) ---
LU24_SOURCE = "https://maps.scag.ca.gov/scaggis/rest/services/LDX/Existinglanduse_poly_OR/MapServer/0?f=json"
LU24_LABELS = {
    "1100": "Residential", "1110": "Single Family Residential",
    "1111": "High Density Single Family Residential", "1112": "Medium Density Single Family Residential",
    "1113": "Low Density Single Family Residential", "1120": "Multi-Family Residential",
    "1121": "Mixed Multi-Family Residential", "1122": "Duplexes, Triplexes and 2- or 3-Unit Condominiums and Townhouses",
    "1123": "Low-Rise Apartments, Condominiums, and Townhouses", "1124": "Medium-Rise Apartments and Condominiums",
    "1125": "High-Rise Apartments and Condominiums", "1130": "Mobile Homes and Trailer Parks",
    "1131": "Trailer Parks and Mobile Home Courts, High-Density", "1132": "Mobile Home Courts and Subdivisions, Low-Density",
    "1140": "Mixed Residential", "1150": "Rural Residential",
    "1200": "Commercial and Services", "1210": "General Office Use", "1211": "Low- and Medium-Rise Major Office Use",
    "1212": "High-Rise Major Office Use", "1213": "Skyscrapers", "1220": "Retail Stores and Commercial Services",
    "1221": "Regional Shopping Center", "1222": "Retail Centers (Non-Strip With Contiguous Interconnected Off-Street Parking)",
    "1223": "Retail Strip Development", "1230": "Other Commercial", "1231": "Commercial Storage",
    "1232": "Commercial Recreation", "1233": "Hotels and Motels", "1240": "Public Facilities",
    "1241": "Government Offices", "1242": "Police and Sheriff Stations", "1243": "Fire Stations",
    "1244": "Major Medical Health Care Facilities", "1245": "Religious Facilities", "1246": "Other Public Facilities",
    "1247": "Public Parking Facilities", "1250": "Special Use Facilities", "1251": "Correctional Facilities",
    "1252": "Special Care Facilities", "1253": "Other Special Use Facilities", "1260": "Educational Institutions",
    "1261": "Pre-Schools/Day Care Centers", "1262": "Elementary Schools", "1263": "Junior or Intermediate High Schools",
    "1264": "Senior High Schools", "1265": "Colleges and Universities",
    "1266": "Trade Schools and Professional Training Facilities", "1270": "Military Installations",
    "1300": "Industrial", "1310": "Light Industrial", "1311": "Manufacturing, Assembly, and Industrial Services",
    "1312": "Motion Picture and Television Studio Lots", "1313": "Packing Houses and Grain Elevators",
    "1314": "Research and Development", "1320": "Heavy Industrial", "1321": "Manufacturing",
    "1322": "Petroleum Refining and Processing", "1323": "Open Storage", "1324": "Major Metal Processing",
    "1325": "Chemical Processing", "1330": "Extraction", "1340": "Wholesaling and Warehousing",
    "1400": "Transportation, Communications, and Utilities", "1410": "Transportation", "1411": "Airports",
    "1412": "Railroads", "1413": "Freeways and Major Roads", "1414": "Park-and-Ride Lots",
    "1415": "Bus Terminals and Yards", "1416": "Truck Terminals", "1420": "Communication Facilities",
    "1430": "Utility Facilities", "1431": "Electrical Power Facilities", "1432": "Solid Waste Disposal Facilities",
    "1433": "Liquid Waste Disposal Facilities", "1434": "Water Storage Facilities",
    "1435": "Natural Gas and Petroleum Facilities", "1436": "Water Transfer Facilities",
    "1437": "Improved Flood Waterways and Structures", "1438": "Mixed Utilities", "1440": "Maintenance Yards",
    "1500": "Mixed Commercial and Industrial", "1600": "Mixed Residential and Commercial",
    "1610": "Residential-Oriented Residential/Commercial Mixed Use",
    "1620": "Commercial-Oriented Residential/Commercial Mixed Use", "1700": "Under Construction",
    "1800": "Open Space and Recreation", "1810": "Golf Courses", "1820": "Local Parks and Recreation",
    "1830": "Regional Parks and Recreation", "1840": "Cemeteries", "1880": "Other Open Space and Recreation",
    "1890": "Off-Street Trails", "1900": "Urban Vacant", "2000": "Agriculture", "2600": "Other Agriculture",
    "3000": "Vacant", "3100": "Vacant Undifferentiated", "3200": "Abandoned Orchards and Vineyards",
    "3300": "Vacant With Limited Improvements", "3400": "Beaches (Vacant)", "4000": "Water",
    "7777": "Specific Plan", "8888": "Undevelopable or Protected Land", "9999": "Unknown",
}
LU_VACANT = {"1900", "3000", "3100", "3200", "3300"}
LU_SURFACE_PARKING = {"1247", "1414"}  # Public Parking Facilities, Park-and-Ride Lots
LU_RELIGIOUS = {"1245"}


def lu_label(code):
    return LU24_LABELS.get(code or "", "Unknown / blank")


def lu_family(code):
    """residential | commercial | industrial | transport | mixed | open_space | agriculture | vacant | water | unknown"""
    c = code or ""
    if c in LU_VACANT:
        return "vacant"
    if c.startswith("11"):
        return "residential"
    if c.startswith("12"):
        return "commercial"
    if c.startswith("13"):
        return "industrial"
    if c.startswith("14"):
        return "transport"
    if c[:2] in ("15", "16", "17"):
        return "mixed"
    if c.startswith("18") or c == "8888":
        return "open_space"
    if c.startswith("2"):
        return "agriculture"
    if c.startswith("4"):
        return "water"
    return "unknown"


# --- Santa Ana zoning: ASSUMPTION, to confirm against the Santa Ana municipal code (Ch. 41) ---
ZONING_LABEL = "ASSUMPTION: mapping to be confirmed against the Santa Ana municipal code"
ZONE_FAMILIES = {
    "single_family": {"R1"},
    "multifamily": {"R2", "R3", "R4"},
    "commercial": {"C1", "C2", "C5", "P"},
    "industrial": {"M1", "M2"},
    "open_space": {"O", "A1"},
}
ZONE_FAMILY_LABEL = {
    "single_family": "Single-family residential", "multifamily": "Multifamily residential",
    "commercial": "Commercial / office", "industrial": "Industrial", "open_space": "Open space / public",
}


def zone_family(city_code):
    """Exact match on the base code (text before '-'), so 'C1-MD' -> commercial but 'OZ1' is unmapped."""
    base = (city_code or "").strip().upper().split("-")[0]
    for fam, codes in ZONE_FAMILIES.items():
        if base in codes:
            return fam
    return None
