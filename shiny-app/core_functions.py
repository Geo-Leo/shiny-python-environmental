from ipyleaflet import GeoData, GeoJSON, Marker, Icon, LayerGroup
from ipywidgets import HTML
import geopandas as gpd, pandas as pd, numpy as np, json
#from shapely.ops import transform
#from pyproj import Transformer
from shapely import wkb


# Function to update site layout map
def update_site(s, gpkg_path):
    print("Updating site layout map...")
    
    # Create geodataframe for locations layer using gpkg file
    loc = gpd.read_file(gpkg_path, layer="gis_locations")
    
    # Load images for well and probe icons
    well = 'mw.png'
    probe = 'vp.png'

    # Add marker for each location location_markers layer group
    location_markers = LayerGroup(name='Location')
    for i in range(0, len(loc)):
        # Create marker using LATITUDE and LONGITUDE values
        location = (loc['LATITUDE'][i], loc['LONGITUDE'][i])
        # Set icon based on location class
        if loc['FIELD_TYPE'][i] == 'MW':
            icon = Icon(icon_url=well, icon_size=[26, 26], icon_anchor=[13, 13])
        else:
            icon = Icon(icon_url=probe, icon_size=[26, 26], icon_anchor=[13, 13])
        marker = Marker(location=location, icon=icon, draggable=False)
        # Create popup for each marker
        marker.popup=HTML(f"""<b>{loc['FIELD_NAME'][i]}</b><br>
                          <b>LATITUDE:</b> {round(loc['LATITUDE'][i], 4)}<br> 
                          <b>LONGITUDE:</b> {round(loc['LONGITUDE'][i], 4)}""")
        location_markers.add(marker)

    s.add(location_markers)  # Add locations_markers to map

    # Zoom to bounding box in map
    tb = loc.total_bounds
    bbox = [ [tb[1], tb[0]], [tb[3], tb[2]] ]
    s.fit_bounds(bbox)


# Function to update map of results 
def update_map(eng, gpkg_path, analyte, depth, nd, soil_layer):
    print("Updating map of results...")
    # Set value for nd_str (non-detect string)
    if nd == 'All':
        nd_str = ''  # Empty string add to end of query so that all points are returned
    elif nd == 'Detect only':
        nd_str = "AND a.nd = 'D'"  # Detect string to add to end of query so that only detections are returned
    else:
        nd_str = "AND a.nd = 'ND'"  # Detect string to add to end of query so that only non-detections are returned
    
    # Create query based on user input selection
    query = f"""
        SELECT a.location, a.analyte, a.value, a.label, a.label2, a.nd, a.depth, a.geom
        FROM view_soilvapor a
        WHERE (a.dup = 'O' OR a.dup = '') AND a.analyte = \'{analyte}\' AND a.depth = \'{depth}\' {nd_str}
        ORDER BY a.id ASC;
    """

    # Create soil_vapor geodataframe using query
    df = pd.read_sql(query, eng)
    df["geometry"] = df["geom"].apply(gpkg_to_geom)
    soil_vapor = gpd.GeoDataFrame(df, geometry="geometry")  
    soil_vapor.drop(columns=["geom"], inplace=True)

    # Create html object to display in results page based on whether query returns results or not
    if len(soil_vapor) == 0:
        # Set html message if no results are returned for query
        msg = "No results found for this selection. Please adjust your selection and try again."
        html = HTML(f"""<h4>{msg}</h4>""")
    else:
        # Set initial html message for hover over effect
        html = HTML("""<h4>Hover over a location</h4>""")
    html.layout.margin = "0px 30px 0px 10px"

    # Define function to update the html when location is hovered over
    def update_html(feature, **kwargs):
        #print("Updating html for hover over effect...")
        if feature["properties"]["Label2"]:
            html.value = """
                <h3><b>{}</b></h3>
                <h4>Analyte: {}</h4> 
                <h4>Value: {} ({})</h4>
                <i>({}) = duplicate sample</i><br>
                <i>Units in micrograms per cubic meter (μg/m^3)</i>
            """.format(
                feature["properties"]["Location"],
                feature["properties"]["Analyte"],
                feature["properties"]["Label"], 
                feature["properties"]["Label2"], 
                feature["properties"]["Label2"])
        else:
            html.value = """
                <h3><b>{}</b></h3>
                <h4>Analyte: {}</h4> 
                <h4>Value: {}</h4>
                <i>Units in micrograms per cubic meter (μg/m^3)</i>
            """.format(
                feature["properties"]["Location"],
                feature["properties"]["Analyte"],
                feature["properties"]["Label"])
            
    # Define function to set style options for each location
    def analyte_style(feature, **kwargs):
        #print("Setting style options for each location...")
        val = feature["properties"]["Value"]
        if val == -1:
            radius = 8
            color = '#E1E1E1'  # Gray
        elif val == 0.0:  
            radius = 10
            color = '#4CE600'  # Green
        elif val in range(1, 1001):  
            radius = 12
            color = '#FFFF00'  # Yellow
        elif val in range(1001, 10001):  
            radius = 14
            color = '#FFAA00'  # Orange
        elif val in range(10001, 100001):  
            radius = 16
            color = '#E60000'  # Red
        elif val in range(100001, 1000001):  
            radius = 18
            color = '#730000'  # Maroon
        else:
            radius = 20
            color = '#4C0073'  # Purple
        return {'radius': radius, 'fillColor': color}

    # Convert soil_vapor geodataframe to json and create a GeoJSON object
    data = json.loads(soil_vapor.to_json())
    geo_data = GeoJSON(data=data,
                       hover_style={'fillColor': '#00ffff' , 'fillOpacity': 0.5},
                       point_style={'radius': 5, 'color': 'black', 'fillOpacity': 0.5, 'fillColor': 'blue', 'weight': 0.9},
                       style_callback=analyte_style
                    )
    
    geo_data.on_hover(update_html)  # Set on hover effect using update_html function
    soil_layer.clear()  # Clear soil_layer currently on map
    soil_layer.add(geo_data)  # Add new soil_layer based on query
   
    return html  # Return html object to display in results page


# Function to add boundary line layer to map
def add_boundary(s, gpkg_path):    
    print("Adding boundary line layer to map...")
    
    # Create geodataframe for boundary layer using gpkg file
    boundary = gpd.read_file(gpkg_path, layer='boundary')

    # Convert boundary geodataframe to json and create a GeoJSON object
    geo_data = GeoData(geo_dataframe = boundary,
                style={'color': 'blue', 'opacity':0.75, 'weight':3},
                name = 'G2 parcel')
    s.add(geo_data)


# Function to convert gpkg geometry blob to shapely geometry
def gpkg_to_geom(blob):
    if blob is None:
        return None
    
    # GeoPackage header is variable length, but WKB starts after byte 8 + envelope
    flags = blob[3] # Byte 3 (flags) tells if envelope exists
    envelope_indicator = (flags >> 1) & 0b111
    
    # Envelope sizes (per GeoPackage spec)
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    envelope_size = envelope_sizes.get(envelope_indicator, 0)
    wkb_start = 8 + envelope_size # 8-byte header + envelope

    return wkb.loads(blob[wkb_start:])

# Function to convert gpkg geometry blob to shapely geometry
def create_loc_dict():
    loc_dict = {'': (34.0986, -118.2397), 
    'MW-2': (34.0955223, -118.2372333),
    'MW-3': (34.1013686, -118.2415541),
    'MW-4': (34.0996559, -118.2376032),
    'MW-5': (34.0965553, -118.2353979),
    'MW-6': (34.0952699, -118.236655),
    'MW-7': (34.0994236, -118.2404784),
    'MW-8': (34.0971445, -118.2386746),
    'MW-9': (34.0955472, -118.2372538),
    'MW-10': (34.094878, -118.2373881),
    'MW-11': (34.094723, -118.2369615),
    'MW-12': (34.0947797, -118.2357593),
    'MW-14': (34.0999434, -118.2395763),
    'MW-15': (34.09707374, -118.2417017),
    'SG-1': (34.09930949, -118.2409687),
    'SG-2': (34.09950971, -118.2413806),
    'SG-3': (34.09812997, -118.2397154),
    'SG-4': (34.09693752, -118.2393225),
    'SG-5': (34.09526598, -118.2374305),
    'SG-6': (34.09503128, -118.2350667),
    'SG-7': (34.10018531, -118.2406071),
    'SG-8': (34.09658309, -118.2376937),
    'SG-9': (34.09508897, -118.2358113),
    'SG-10': (34.09507756, -118.237349),
    'SG-11': (34.09609759, -118.2363801),
    'SG-12': (34.09653595, -118.2370908),
    'SG-13': (34.10051462, -118.2407703),
    'SG-14': (34.10020697, -118.2411342),
    'SG-15': (34.10095197, -118.2407486),
    'SG-16': (34.10020748, -118.2402598),
    'SG-17': (34.09574598, -118.2361239),
    'SG-18': (34.09461064, -118.2357967),
    'SG-19': (34.09630844, -118.2390295),
    'SG-20': (34.09792623, -118.2380522),
    'SG-21': (34.09955757, -118.2403053),
    'SG-22': (34.09641083, -118.2380253),
    'SG-23': (34.09728726, -118.2391205),
    'SG-24': (34.09515912, -118.2368775),
    'SG-25': (34.09792736, -118.2395803),
    'SG-28': (34.09776802, -118.2394593),
    'SG-29': (34.10053379, -118.2404722),
    'SG-30': (34.09904841, -118.240566),
    'SG-31': (34.09760737, -118.2392075),
    'SG-32': (34.09963746, -118.2399653),
    'SG-33': (34.09755834, -118.2381551),
    'SG-34': (34.09621714, -118.2369242),
    'SG-35': (34.09564231, -118.2380587),
    'SG-36': (34.09724809, -118.2395157),
    'SG-37': (34.09712495, -118.237939),
    'SG-38': (34.09935051, -118.2393126),
    'SG-39': (34.09902788, -118.2398073)}
    return loc_dict