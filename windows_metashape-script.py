##Written by Jeffrey Gillan, University of Arizona, 2019
##This python script (python3) uses Agisoft Metashape to generate point clouds, orthomosaics, DSMs, and DTMs from a set of overlapping drone images. It runs in headless mode, meaning the user never has to open the Metashape GUI.
##This script should be deployed from the Windows command prompt.
##Type the following two lines of code into the command prompt. The first path (on the 2nd line) is the location of this python file. The second path is the location of drone images and the psx file.

##cd C:\Program Files\Agisoft\Metashape Pro
##metashape.exe -r "F:\ecostate_mapping\metashape.py" "F:\ecostate_mapping\35b_u2"

##If you want to do multiple projects back-to-back, add additional paths specifying the location of images and psx files
##For example:
	##metashape.exe -r "F:\ecostate_mapping\metashape.py" "F:\ecostate_mapping\35b_u2" "F:\ecostate_mapping\2a_u1"


import os
import Metashape, sys

#####################################################################################

##this line is pointing to the path of drone photos that you specified in the Command Prompt code
path_photos = sys.argv[1]


# set new working directory to be in working folder set in command line
os.chdir(path_photos)


##Define: PhotoScan Project File
MetashapeProjectFile = ".\\Metashape_Project.psx"
##get main app objects
doc = Metashape.Document()

#Create a new psx
doc.save(MetashapeProjectFile)

#Open an existing psx
#doc.open(MetashapeProjectFile)

app = Metashape.Application()

## create chunk
chunk = doc.addChunk()

## loading images
image_list = os.listdir(path_photos)
photo_list = list()
for photo in image_list:
    if ("jpg" or "jpeg" or "JPG" or "JPEG") in photo.lower():
        photo_list.append(path_photos + "/" + photo)
chunk.addPhotos(photo_list)

##This loads the accuracy of the camera position at time of exposure (stored in the image exif). If you don't do this, Agisoft will assume 10 m accuracy. The accuracy of the RTK drone images is generally 1-2 cm.
chunk.loadReferenceExif(load_rotation=True, load_accuracy=True)

##SAVE PROJECT
doc.save()


## Set up all GPUs to work (not sure if this is necessary)
## from http://www.agisoft.com/forum/index.php?topic=9874.0
## Enable two GPUs
Metashape.app.gpu_mask = 3


## align photos with generic preselection=True, reference preselection=true, key point limit=50000, tie point limit=0, adaptive camera model fitting=true
chunk.matchPhotos(Metashape.MediumAccuracy, Metashape.ReferencePreselection, keypoint_limit=50000, tiepoint_limit=0)
chunk.alignCameras(adaptive_fitting=True)
doc.save()

##Gradual Selection of poor quality points in the sparse cloud are identified and deleted. Cameras are optimzed after each filter.
threshold_uncertainty = 13
f = Metashape.PointCloud.Filter()
f.init(chunk, criterion = Metashape.PointCloud.Filter.ReconstructionUncertainty)
f.removePoints(threshold_uncertainty)

chunk.optimizeCameras(adaptive_fitting=True)

doc.save()

threshold_proj = 10
g = Metashape.PointCloud.Filter()
g.init(chunk, criterion = Metashape.PointCloud.Filter.ProjectionAccuracy)
g.removePoints(threshold_proj)

chunk.optimizeCameras(adaptive_fitting=True)


threshold_repro = 0.25
h = Metashape.PointCloud.Filter()
h.init(chunk, criterion = Metashape.PointCloud.Filter.ReprojectionError)
h.removePoints(threshold_repro)

chunk.optimizeCameras(adaptive_fitting=True)

doc.save()

##Build DEM with sparse cloud. If you want to build DEM with dense cloud, move this command below #build dense point cloud, and add parameter 'source=DenseCloudData'
chunk.buildDem(interpolation=Metashape.EnabledInterpolation)
doc.save()

##Build dense point cloud
chunk.buildDepthMaps(quality=Metashape.HighQuality, filter=Metashape.MildFiltering)

task = Metashape.Tasks.BuildDenseCloud()
task.network_distribute = True
task.apply(chunk)

doc.save()

##Disable all images that have 30 degree pitch while keeping all nadir images.This is to reduce processing time for orthomosaic creation.
camera = chunk.cameras[1]
T = chunk.transform.matrix
m = chunk.crs.localframe(T.mulp(camera.center))
for camera in chunk.cameras:
	R = (m * T * camera.transform * Metashape.Matrix().Diag([1, -1, -1, 1])).rotation()
	estimated_ypr = Metashape.utils.mat2ypr(R)
	if abs(estimated_ypr[1]) > 10:
		camera.enabled = False
	else:
		camera.enabled = True

doc.save()

##Make the orthomosaic
chunk.buildOrthomosaic(surface=Metashape.ElevationData, blending=Metashape.MosaicBlending, fill_holes=True)
doc.save()

##Export orthomosaic in WGS 84
chunk.exportOrthomosaic("F:/ecostate_mapping_Aug_Sept2019/22_2/products/22_2_ortho.tif", projection=Metashape.CoordinateSystem("EPSG::4326"), dx=1.05623e-07, dy=9.01846e-08, write_alpha=False)

# Duplicate Chunk
chunk2 = chunk.copy()

##Build DEM with dense point cloud (all points)
chunk2.buildDem(interpolation=Metashape.EnabledInterpolation, source=Metashape.DenseCloudData)
doc.save()

#Export DSM
chunk2.exportDem("F:/ecostate_mapping_Aug_Sept2019/22_2/products/22_2_DSM.tif", projection=Metashape.CoordinateSystem("EPSG::4326"), dx=1.05623e-07, dy=9.01846e-08)


##Use Color to select only ground points
chunk2.dense_cloud.selectPointsByColor(color=[255, 220, 178], tolerance=51, channels='RGB')


##Remove all points that are not ground
chunk2.dense_cloud.cropSelectedPoints()

##Filter out tall vegetation points using the Classify ground points tool. Bare-ground and some grasses remain
chunk2.dense_cloud.classifyGroundPoints(max_angle=3.0, max_distance=0.09, cell_size=4.0)
doc.save()


##Build DTM with dense point cloud (just ground points)
chunk2.buildDem(interpolation=Metashape.EnabledInterpolation, source=Metashape.DenseCloudData, classes=[2])
doc.save()

##Export DTM
chunk2.exportDem("F:/ecostate_mapping_Aug_Sept2019/22_2/products/22_2_DTM.tif", projection=Metashape.CoordinateSystem("EPSG::4326"), dx=1.05623e-07, dy=9.01846e-08)


##Export dense point cloud in WGS 84 UTM zone 12n
chunk.exportPoints("F:/ecostate_mapping_Aug_Sept2019/22_2/products/22_2_highdensity.las", projection=Metashape.CoordinateSystem("EPSG::32612"))

##Export only ground points from the dense cloud
#chunk.exportPoints("F:/ecostate_mapping/35b_u2/nadir/densepoints_ground.las", projection=Metashape.CoordinateSystem("EPSG::32612"), classes=[2])

##############################################################################################################################

##this line is pointing to the path of drone photos that you specified in the Command Prompt code
#path_photos = sys.argv[2]