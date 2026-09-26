from shiny import reactive, render
from shiny.express import input, ui, output
from shinywidgets import render_widget
from ipyleaflet import Map, basemaps, LayersControl, LegendControl, CircleMarker, LayerGroup, Popup, ScaleControl
from ipywidgets import Label, HTML
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from core_functions import update_site, update_map, add_boundary, create_loc_dict
from pathlib import Path
import psycopg2
import geopandas as gpd, numpy as np, json
from ipyleaflet import GeoData, GeoJSON, Marker, Icon, LayerGroup
from ipywidgets import HTML
from pathlib import Path


# Path to your GeoPackage file
gpkg_path = Path("taylor_yard.gpkg")

# Function to create sqlalchemy engine
def engine():
    global user, password, host, port, database, schema, gpkg_path
    user = input.user()
    password = input.pw()
    host = input.host()
    port = input.port()
    database = input.db()
    schema = input.schema()
    #db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    gpkg_str = (f"sqlite:///{gpkg_path.resolve()}")
    eng = create_engine(gpkg_str)
    return eng

# Reactive effect to test if database connnection is valid after pressing connection button
@reactive.effect
@reactive.event(input.con_button)
def con_button():
    global eng
    eng = engine()
    try:
        print('Testing database connection...')
        with eng.connect() as conn:
            ui.notification_show('Testing database connection...', duration=1)
            db = conn.execute(text("SELECT current_database()"))
            print('db')
            msg = f'Connected to {db.scalar_one()} successfully.'

    except SQLAlchemyError as e:
        msg = 'Did not connect to database. Change input in text boxes and try again.'
        print(f"Error: {e}")
    ui.notification_show(msg, duration=3)

# Create location dictionary with location name as keys and LATITUDE/ LONGITUDE coordinates as values
loc_dict = create_loc_dict()

# Create sidebar layout to organize database connection configuration interface 
with ui.sidebar(open="closed", bg="#f8f8f8"):
    with ui.accordion(id="acc", open=False):  
        with ui.accordion_panel("Configure database connection"):  
            ui.input_text("user", "Username:", "avnadmin")  
            ui.input_password("pw", "Password:", value='AVNS_exJUZgrVHAHXlWI_b5B')
            ui.input_text("host", "Host:", "pg-1afe4b7c-leo-7d4e.b.aivencloud.com")  
            ui.input_text("port", "Port:", "10563")  
            ui.input_text("db", "Database:", "defaultdb")
            ui.input_text("schema", "Schema:", "tayloryard")
            ui.input_action_button("con_button", "Test database connection")

ui.page_opts(fillable=True)

# Create site background page with backgournd information
with ui.nav_panel("Site background"):
    # Use markdown to render html in page
    ui.markdown('# Taylor Park - Environmental sampling results')
    ui.markdown("""Taylor Yard is in Northeast Los
    Angeles. It runs along the Los Angeles River between
    the Glendale Freeway and Figueroa Street. It was used
    as a railroad maintenance yard before being split up
    and sold as parcels.""")      
    ui.markdown("""The G2 Site is the southern 42 acres of
    Taylor Yard. Its soil is contaminated with multiple
    chemicals from historical operations. The City of Los
    Angeles (City) bought the Site in 2017 to restore
    habitat and create public access to the river.
    In January 2018, the City signed a California Land
    Reuse and Revitalization Agreement (CLRRA) with
    Department of Toxic Substances Control (DTSC) to investigate and clean up G2.""")
    ui.markdown("""The City of Los Angeles recently acquired the Site and began 
    an investigation which included soil, soil gas, and groundwater 
    sampling to determine the extent of contamination present. The 
    DTSC oversaw the investigation as part of the CLRRA with the City.""")
    ui.markdown("**What type of work was done?**")
    ui.markdown("""Soil gas samples were collected from 39 soil vapor probes and 13 monitoring wells 
    (with co-located soil vapor probes) ranging from 
    3-5 feet (shallow) to 15-20 feet (deep) below ground surface.""")
    ui.markdown("""Sampling conducted was for volatile
    organic compounds to determine the extent of the contamination found at the site.""")
    ui.markdown("**Why was this site sampled?**")
    ui.markdown("""The site was used for more than 80 years for rail
    maintenance and fueling. Plans for the site include
    recreational space. Sampling was conducted to ensure safety for future use and 
    determine the cleanup options.""")
    ui.markdown("**What will happen to the soil gas probes drilled at the site?**")
    ui.markdown("""The probes were used to
        collect samples of soil gas and, in some cases, remove
        contaminated air from the soil as part of a
        treatment process. Some of these are no longer useful
        and will be abandoned under DTSC's oversight and
        approval. This will happen during the construction
        phase of the Paseo del Rio at Taylor Yard Project.""")
    ui.markdown('#### Taylor Yard G2 Parcel - 2850 Kerr Street, Los Angeles, CA 90039')
    # Render image of the site from a city publication
    @render.image
    def image():
        dir = Path(__file__).resolve().parent
        img = {"src": str(dir / "taylor_yard_publication.jpg"), "width": "900px"}
        return img
    
# Create site layout page and organize it into layout with two columns    
with ui.nav_panel("Web map of site layout"):
    with ui.layout_columns(col_widths=(9, 3)):
        # Create first column containing the Leaflet map
        with ui.card(full_screen=True):
            @render_widget
            def site(): 
                global s
                # Add site layout map
                s = Map(zoom=15, min_zoom=15, center=(34.0986, -118.2397), basemap=basemaps.Esri.WorldTopoMap, scroll_wheel_zoom=True)
                s.add( LayersControl(position='topright'))  # Add layers control to map

                # Add popup with directions for user
                popup = Popup(
                    name='Instructions',
                    location=(34.0986, -118.2397),
                    child=HTML(value='<h5>Click on a marker to display popup.</h5>'),
                    close_button=False,
                    auto_close=True,
                    close_on_escape_key=False
                )
                s.add(popup)

                # Add site boundary layer to map 
                global eng
                eng = engine()
                add_boundary(s, gpkg_path)

                s.add(ScaleControl(position='bottomleft', metric=False))  # Add scale control to map

                # Add soil vapor and monitoring wells to map
                update_site(s, gpkg_path)
                return s
            
        # Create second column containing the legend, input selection widget, and information in html
        with ui.panel_absolute():    
            @render_widget
            def text2():
                probe = 'vp.png'
                well = 'mw.png'
                html_text = HTML()
                html_text.value = '<h3>Legend</h3>'\
                f'<img src={probe} alt="probe" width="25" height="25">' + '<span style="font-size:21px">  Vapor probe</span>' + '<br>'\
                f'<img src={well} alt="well" width="25" height="25">' + '<span style="font-size:21px">  Monitoring well</span>' + '<br><br>'
                html_text.layout.margin = "0px 20px 20px 20px"
                return html_text
                
            ui.input_selectize('loc', "Zoom to location", choices=list(loc_dict.keys()))

            @render_widget
            def text3():
                md1 = HTML(value="<br><h6>There are 13 monitoring well (with co-located soil vapor probe) and 39 soil vapor probe locations.</h6>\
                           <h6>They were sampled on 1/30/2024 for various analytes. The web app displays the results for PCE and TCE only.</h6>") 
                md1.layout.margin = "0px 30px 0px 10px"
                return md1
            
# Create results page and organize it into layout with two columns    
with ui.nav_panel("Web map of results"):
    with ui.layout_columns(col_widths=(9, 3)):
        # Create first column containing the Leaflet map
        with ui.card(full_screen=True):
            @render_widget
            def map(): 
                global m
                # Add results map
                m = Map(zoom=15, min_zoom=15, center=(34.0986, -118.2397), basemap=basemaps.Esri.WorldImagery, scroll_wheel_zoom=True)

                # Add popup with directions for user
                popup = Popup(
                    name='Instructions',
                    location=(34.0986, -118.2397),
                    child=HTML(value='<h5>Select values for analyte, depth, and detect type. Then press update button.</h5>'),
                    close_button=False,
                    auto_close=True,
                    close_on_escape_key=False
                )
                m.add(popup)

                # Add site boundary to map
                global eng
                eng = engine()
                add_boundary(m, gpkg_path)

                # Add empty soil_layer to map
                global soil_layer
                soil_layer = LayerGroup(name="Soil vapor")
                m.add(soil_layer)

                m.add(LayersControl(position='topright'))  # Add layers control to map

                # Add legend control to map
                legend = LegendControl({"No flow": "rgba(225, 225, 225, 0.7)", 
                            "Non detect": "rgba(76, 230, 0, 0.7)", 
                            "1-1,000": "rgba(255, 255, 0, 0.7)", 
                            "1,001-10,000": "rgba(255, 170, 0, 0.7)", 
                            "10,001-100,000": "rgba(230, 0, 0, 0.7)", 
                            "100,001-1,000,000": "rgba(115, 0, 0, 0.7)", 
                            ">1,000,000": "rgba(76, 0, 115, 0.7)", 
                            }, title="Value", position="bottomright")
                m.add(legend)
                m.add(ScaleControl(position='bottomleft', metric=False))  # Add scale control to map
                return m
        
        # Create second column containing update button, input selections, and the html label for each location
        with ui.panel_absolute():
            ui.input_action_button("update_button", "Update map")
            @render_widget
            def text6():
                md1 = HTML(value="<br>")
                return md1
            
            ui.input_select('analyte', "Analyte", ['PCE', 'TCE'])
            ui.input_select('depth', "Depth", ['Deep', 'Shallow'])
            ui.input_select('nd', "Detect type", ['All', 'Detect only', 'Non-detect only'])

            # Reactive event to update leaflet map after update button is pressed and display the html label for each location
            @render_widget
            @reactive.calc
            @reactive.event(input.update_button)
            def connect():
                analyte = input.analyte()
                depth = input.depth()
                nd = input.nd()
                results_html = update_map(eng, gpkg_path, analyte, depth, nd, soil_layer)
                return results_html

global zoom_marker
zoom_marker = None
# Add reactive effect for site map
@reactive.effect
def _(): 
    site.widget.center = loc_dict[input.loc()]  # Zoom to location of drop-down selection when using its coodinates
    circle_marker = CircleMarker()
    circle_marker.location = loc_dict[input.loc()]  # Create circle marker at location 

    # Specify radius, weight, and color of circle marker
    circle_marker.radius = 14
    circle_marker.weight = 3
    circle_marker.color = "red"

    global zoom_marker
    # Create new zoom marker layer
    if zoom_marker:
        zoom_marker.clear()
    zoom_marker = LayerGroup(name="Zoom marker")    
    
    global s
    # Add circle marker to zoom marker layer 
    if input.loc():
        zoom_marker.add(circle_marker)

    s.add(zoom_marker)  # Add zoom marker layer to map