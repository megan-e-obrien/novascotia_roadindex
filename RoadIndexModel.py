# Code purpose: A Road Index Model for Nova Scotia, developed by the Nova Scotia Department of Natural Resources and Renewables (DNRR)
# https://novascotia.ca/natr/
# Author: Megan O'Brien
# Date: December, 2024

import arcpy
import os
import sys
from arcpy import env
from arcpy.sa import *
print("Packages imported")

###################################################################################################################
# To run this code, the following file paths must be updated:
# (1) Workspace - the folder that output files will be saved to.
env.workspace = r'Your file path here'

# (2) File for province county boundaries. Available from https://data.novascotia.ca/
nsCounties = r'Your file path here'
userDefinedExtent = False

# (3) If using a custom extent polygon other than the entire province. User-generated.
# If NOT using, comment out this block
extent = r'Your file path here'
userDefinedExtent = True

# (4) Files for Nova Scotia Road Network (NSRN) and Nova Scotia Topographic Database - Utilities. Both files are
#     required to successfully run the code. Available from https://data.novascotia.ca/
NSTDB_NSRN = r'Your file path here'
NSTDB_UT = r'Your file path here'

###################################################################################################################

# Check if Spatial Analyst extension is available. If available, check out extension.
if arcpy.CheckExtension('Spatial') == 'Available':
    arcpy.CheckOutExtension('Spatial')
    print("Checked out Spatial Extension")
else:
    print("Spatial Analyst license is unavailable - check License settings in ArcGIS Pro to see how many licenses there are")
    sys.exit()

inputs = [NSTDB_NSRN, NSTDB_UT]
inputnames = ["NSTDB_NSRN", "NSTDB_UT"]
inputcount = 0
inputname = ""

# Set project parameters - output coordinate system, overwrite to true, cell size to 100 m (1 ha).
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference("NAD 1983 CSRS UTM Zone 20N")
env.overwriteOutput = True
arcpy.env.cellSize = 100
print("Environments set, spatial reference set to NAD 1983 CSRS UTM Zone 20N")

# Define output workspaces. All final output files will have the prefix "Output_".
out_workspace = (env.workspace + r'\Output_')

# Dissolve Nova Scotia counties into provincial boundary layer.
boundaryOutput = (out_workspace + 'NSBoundaries.shp')
nsBoundary = arcpy.management.Dissolve(nsCounties, boundaryOutput)

# Depending on whether the user sets a custom extent or uses the provincial boundaries, set the project extent.
if userDefinedExtent:
    arcpy.env.extent = extent
    print("Extent set to user-defined polygon")
else:
    arcpy.env.extent = boundaryOutput
    print("Extent set to province of Nova Scotia")

# Define an expression used to classify the feature codes in the NSTDB_NSRN layer.
field_name = "Road_Index"
expression = "classify(!feat_code!, !street!)"
code_block = """
def classify(featcode, street):
    trails = ['AB', 'RRRD54', 'RRRR54', 'RRRDTK5', 'RRRDTR',
    'RRBRAB', 'RRBR54', 'RRBRTK5', 'RRBRTR50', 'RRTUTK50']
    gravelroads = ['RRRDMC', 'RRRDRA', 'RRRDSL',
    'RRRR5', 'RRBRLODWZ2', 'RRBRRADWZ2', 'RRRDLODWZ2', 'RRRDRADW', 'RRBRMC', 'RRBRRA', 'RRBRSL', 'RRBRDW5', 'RRDM', 'RRTURADWZ2', 'RRTULOZ2', 'RRTUSL']
    pavedroads = ['RRRDAT', 'RRRDCO', 'RRRDLO', 'RRRDRP', 'RRBRAT', 'RRBRCO', 'RRBRRP',
    'RRBRLO', 'RRRDLA', 'RRRDLC', 'RRBRLA', 'RRBRLC', 'RRRDLH',
    'RRBRLH', 'RRTUAT', 'RRBRCO', 'RRTULO', 'RRTURP', 'RRTULA', 'RRTULC', 'RRTULH' ]
    # Divided highways includes 100 series highways
    divided = ['HW', 'TC']
    namedhighways = ['Highway' ]
    
    # minimaldist and unknown cover categories of road not included in the Road Index. They can be run (comments removed) to categorize all available features in NSRN. Otherwise, the Road_Index type will be set to Null
    minimaldist = ['RRRDDR50', 'RRBRDR50', 'RRRDWA', 'RRRDWKAD', 'RRFC50']
    unknown = ['RDTMP', 'RRDHX']
    divided == False
    cc = "Null"
    
    for h in divided:
        if (featcode.__contains__(h)):
            cc = "Highway"
            divided = True
            break
        else:
            divided = False
    
    if (street.__contains__('Highway')):
        cc = "Highway"
        divided = True
    
    for j in trails:
        if (featcode.__contains__(j)):
            cc = "Trail"
            break
    
    for k in gravelroads:
        if (featcode.__contains__(k)):
            cc = "Gravel"
            break
    
    for l in pavedroads:
        if divided:
            break
        elif (featcode.__contains__(l)):
            cc = "Paved"
            break
    
    #for m in minimaldist:
        #if (featcode.__contains__(m)):
            #cc = "MinimalDisturbance"
            #break
    
    #for n in unknown:
        #if(featcode.__contains__(n)):
            #cc = "StatusUnknown"
            #break
    
    return cc"""

# Define an expression used to classify the feature codes in the NSTDB_UT layer.
field_name_UT = "Road_Index"
expression_UT = "classify(!feat_code!)"
code_block_UT = """
def classify(featcode):
    utility = ['UTPI50', 'UTPI57', 'UTTR50']
    cc = "Null"
    
    for i in utility:
        if (featcode.__contains__(i)):
            cc = "Utility"
            break
            
    return cc"""

# The main Road Index function, which will be applied to all feature types. The function calculates the density of linear
# features within 1 km of a 1 ha pixel, and the function of the distance from a 1 ha pixel to the nearest linear feature within 1 km.
# The raster values will then be rescaled to a values between 0 and 10.

def calculations(selectedLayer, value):
    # Measure 1 - density of lines meters per meter squared within a 1 km radius given a 1 ha pixel
    # Set parameters
    inPolylineFeatures = selectedLayer
    populationField = "NONE"
    cellSize = 100
    searchRadius = 1000

    # Run Line Density tool
    outLineDensity = LineDensity(inPolylineFeatures, populationField, cellSize, searchRadius, "SQUARE_METERS")
    print("Line Density tool complete for: " + value)

    # Get minimum and maximum raster values from the Line Density raster, set variables for raster calculation
    density_input = outLineDensity
    density_min = float(arcpy.GetRasterProperties_management(outLineDensity, "MINIMUM").getOutput(0))
    density_max = float(arcpy.GetRasterProperties_management(outLineDensity, "MAXIMUM").getOutput(0))

    # Load the raster
    raster = arcpy.sa.Raster(density_input)

    # Perform the rescaling
    outputDensity = ((raster - density_min) / (density_max - density_min)) * 10

    # Define the rescaled raster as a Raster in arcpy to use for feature score
    scoreDens = arcpy.sa.Raster(outputDensity)

    # Measure 2 - function of the distance from a given 1 ha pixel to the nearest linear feature to a max distance of 1 km
    # Set parameters
    inSource = selectedLayer
    sourceMaxAcc = 1000

    # Run Distance Accumulation Tool
    outDistAcc = DistanceAccumulation(inSource, "", "", "",
                                      "", "", "", "",
                                      "", "", "",
                                      "", sourceMaxAcc, "",
                                      "", "")
    print("Distance Accumulation tool complete for: " + value)

    # Get minimum and maximum raster values from the Line Density raster, set variables for raster calculation
    distance_input = outDistAcc
    distance_min = float(arcpy.GetRasterProperties_management(outDistAcc, "MINIMUM").getOutput(0))
    distance_max = float(arcpy.GetRasterProperties_management(outDistAcc, "MAXIMUM").getOutput(0))

    # Load the raster
    raster = arcpy.sa.Raster(distance_input)

    # Perform the rescaling
    outputDistance = 10 - ((raster - distance_min) / (distance_max - distance_min) * 10)

    scoreDis = arcpy.sa.Raster(outputDistance)

    # Calculate total feature score
    featScore = (scoreDens + scoreDis)/2

    # Save feature score raster
    featScore.save(out_workspace + value + '_Score.tif')

# Add the road index field to the imported NSTDB layers and apply the Field Calculator based on the feature code values.
# ROADS
# Add a new field
arcpy.management.AddField(NSTDB_NSRN, field_name, "TEXT", "", "", 25, "", field_is_nullable="NULLABLE")

# Calculate road index field based on featcode and street names containing the text "Highway"
arcpy.management.CalculateField(NSTDB_NSRN, field_name, expression, "PYTHON3", code_block)

# Save the altered layer as a shapefile to the code results folder
arcpy.CopyFeatures_management(NSTDB_NSRN, (out_workspace + 'NSTDB_NSRN.shp'))

print("New field added to NSTDB_NSRN layer and calculated based on road feature codes.")

# UTILITIES
# Add a new field
arcpy.management.AddField(NSTDB_UT, field_name, "TEXT", "", "", 25, "", field_is_nullable="NULLABLE")

# Calculate road index field based on featcode
arcpy.management.CalculateField(NSTDB_UT, field_name_UT, expression_UT, "PYTHON3", code_block_UT)

# Save the altered layer as a shapefile to the code results folder
arcpy.CopyFeatures_management(NSTDB_UT, (out_workspace + 'NSTDB_UT.shp'))

print("New field added to NSTDB_UT layer and calculated based on road feature codes.")

# Loop through input layers - NSRN & UT - and apply the calculation function to each successive layer.
for input in inputs:
    inputname = inputnames[inputcount]
    inputcount = inputcount+1
    # Set feature class and field of index
    fc = 'Output_' + inputname + '.shp'
    field = 'Road_Index'
    print("Applying Road Index calculations to: " + inputname + "layer")

    # Loop through Road_Index field and find each unique value
    with arcpy.da.SearchCursor(fc, [field]) as cursor:
        uniqueValues = sorted({row[0] for row in cursor})

    # For each unique value, query the layer for each value in a loop
    for value in uniqueValues:
        query = f"{field} = '{value}'"

        if value == 'Null':
            continue
        else:
            print("Applying calculations to: " + value)

            # Select layer by attribute based on current value during this loop
            selectedLayer = arcpy.SelectLayerByAttribute_management(fc, "NEW_SELECTION", query)

            # Save the selected layer as a shapefile to the output folder - e.g. trails, gravel, highway, etc., if desired.
            #input_fc = selectedLayer
            #output_fc = os.path.join(out_workspace + value + ".shp")
            #arcpy.CopyFeatures_management(input_fc, output_fc)

            # Run calculations function on each unique field value
            calculations(selectedLayer, value)

# To calculate the appropriate values for "all features", used to account for all man made linear features regardless
# of type, merge utilities and roads layer, and perform the same calculations on the merged layer
print("Now calculating 'all features' layer")
output_merge = (out_workspace + 'Merged_NSRN_UT.tif')
merged_NSRN_UT = arcpy.management.Merge([NSTDB_NSRN, NSTDB_UT], output_merge)
selectedLayer = merged_NSRN_UT
value = 'Merged_NSRN_UT'

# Call calculations function
calculations(selectedLayer, value)
print("Completed calculating 'all features' layer")

# Define the score value rasters based on previous output from the calculation function
trailScore = (arcpy.sa.Raster('Output_Trail_Score.tif'))
utilityScore = (arcpy.sa.Raster('Output_Utility_Score.tif'))
allFeatureScore = (arcpy.sa.Raster('Output_Merged_NSRN_UT_Score.tif'))
gravelScore = (arcpy.sa.Raster('Output_Gravel_Score.tif'))
pavedRoadScore = (arcpy.sa.Raster('Output_Paved_Score.tif'))
highwayScore = (arcpy.sa.Raster('Output_Highway_Score.tif'))
print("Feature scores created")

# Calculate Road Index raster
roadIndex = (
    Con(IsNull(trailScore), 0, trailScore) +
    Con(IsNull(utilityScore), 0, utilityScore * 3) + 
    Con(IsNull(allFeatureScore), 0, allFeatureScore * 5) + 
    Con(IsNull(gravelScore), 0, gravelScore * 6) + 
    Con(IsNull(pavedRoadScore), 0, pavedRoadScore * 10) +
    Con(IsNull(highwayScore), 0, highwayScore * 15)
)/4

print("Feature score/road index weighted calculations applied")

# Extract final raster by province mask to remove pixel values not on land
roadIndexFloat = ExtractByMask(roadIndex, nsBoundary, "INSIDE")

# Convert the raster values to integers to remove decimal values and allow for raster analysis
roadIndexFinal = Int(roadIndexFloat)

# Rescale the raster values to between 0 and 100 to measure road influence
# Use roadIndexFloat as input to get more accurate results, then convert to an integer
RI_min = float(arcpy.GetRasterProperties_management(roadIndexFloat, "MINIMUM").getOutput(0))
RI_max = float(arcpy.GetRasterProperties_management(roadIndexFloat, "MAXIMUM").getOutput(0))
roadInfluenceFloat = ((roadIndexFloat - RI_min) / (RI_max - RI_min)) * 100

roadInfluenceFinal = Int(roadInfluenceFloat)

# Save final road index as tif file
roadIndexFinal.save(out_workspace + 'RoadIndex.tif')
print("Road index raster saved")

# Save road influence as tif file
roadInfluenceFinal.save(out_workspace + 'RoadInfluence.tif')
print("Road influence raster saved")

# Loop through all files in the folder and check for unnecessary files
# Delete unnecessary files
keywords = ["Extract", "LineDen", "Distanc_Output"]
for filename in os.listdir(env.workspace):
    if any(keyword in filename for keyword in keywords):
        file_path = os.path.join(env.workspace, filename)

        try:
            arcpy.management.Delete(file_path)
            print(f"Deleted: {filename}")
        except Exception as e:
            print(f"Failed to delete {filename}: {e}")

arcpy.management.Delete('Output_NSBoundaries.shp')
arcpy.management.Delete('Output_NSTDB_NSRN.shp')
arcpy.management.Delete('Output_NSTDB_UT.shp')
arcpy.management.Delete('Output_Merged_NSRN_UT.shp')

# Check out spatial analyst extension license
arcpy.CheckInExtension('Spatial')
