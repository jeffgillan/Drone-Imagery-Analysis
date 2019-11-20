#This python script (python3) uses Agisoft Metashape to generate point clouds and orthomosaics from a set of overlapping drone images. It runs in headless mode, meaning the user never has to open the Metashape GUI.
##This script should be deployed from the linux terminal.
##Type the following two lines of code into the terminal. The first path (on the 2nd line) is the location of this python file. The second path is the location of drone images.

##cd /mnt/DATA/DOWNLOADS/SOFTWARE/METASHAPE/metashape-pro
##metashape.sh -r "/xdisk/jgillan/multi_task_network.py" "/xdisk/jgillan/1a_u6"



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
doc.save(MetashapeProjectFile)

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

#Now starts the network (HPC) tasks
path = "\\1a_u6\\Metashape_Project.psx"

network_tasks = list()

### match photos
task = Metashape.Tasks.MatchPhotos()
task.downscale = Metashape.Accuracy.LowAccuracy
task.keypoint_limit = 50000
task.tiepoint_limit = 0
task.preselection_generic = True
task.preselection_reference = True
task.network_distribute = True
n_task = Metashape.NetworkTask()
n_task.name = task.name
n_task.params = task.encode()
n_task.frames.append((chunk.key, 0))
network_tasks.append(n_task)

###align cameras
task = Metashape.Tasks.AlignCameras()
task.adaptive_fitting = True
task.network_distribute = True

n_task = Metashape.NetworkTask()
n_task.name = task.name
n_task.params = task.encode()
n_task.frames.append((chunk.key,0))   # <-----  HERE IS THE F@#%^& ERROR
network_tasks.append(n_task)

client = Metashape.NetworkClient()
client.connect('10.1.2.234')
batch_id = client.createBatch(path, network_tasks)
client.resumeBatch(batch_id)

doc.save()

#These next tasks are NOT run on HPC. I need to figure out how to make them wait for the HPC to finish creating the sparse point cloud. Can I check on the status of
#the HPC initial alignment and write a conditional statement that will start the following commands once the HPC is finished?

##Gradual Selection of poor quality points in the sparse cloud are identified and deleted. Cameras are optimized after each filter.
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

#Build DEM with sparse cloud. If you want to build DEM with dense cloud, move this command below #build dense point cloud, and add parameter 'source=DenseCloudData'
chunk.buildDem(interpolation=Metashape.EnabledInterpolation)
doc.save()

## These next tasks (dense point cloud generation) is an HPC task

### depth maps
task = Metashape.Tasks.BuildDepthMaps()
task.downscale = Metashape.Quality.HighQuality
task.filter_mode = Metashape.FilterMode.MildFiltering
task.network_distribute = True

n_task = Metashape.NetworkTask()
n_task.name = task.name
n_task.params = task.encode()
n_task.frames.append((chunk.key, 0))
network_tasks.append(n_task)

### dense cloud
task = Metashape.Tasks.BuildDenseCloud()
task.point_colors = True
task.network_distribute = True

n_task = Metashape.NetworkTask()
n_task.name = task.name
n_task.params = task.encode()
n_task.frames.append((chunk.key, 0))
network_tasks.append(n_task)


#The rest of the tasks from here to the end are NOT HPC tasks

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
chunk.exportOrthomosaic("/home/jgillan/DATA2/1a_u6/products/1a_u6_ortho.tif", projection=Metashape.CoordinateSystem("EPSG::4326"), dx=1.05623e-07, dy=9.01846e-08, write_alpha=False)

# Duplicate Chunk
chunk2 = chunk.copy()

##Build DEM with dense point cloud (all points)
chunk2.buildDem(interpolation=Metashape.EnabledInterpolation, source=Metashape.DenseCloudData)
doc.save()

#Export DSM
chunk2.exportDem("/home/jgillan/DATA2/products/1a_u6_DSM.tif", projection=Metashape.CoordinateSystem("EPSG::4326"), dx=1.05623e-07, dy=9.01846e-08)


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
chunk2.exportDem("/home/jgillan/DATA2/products/1a_u6_DTM.tif", projection=Metashape.CoordinateSystem("EPSG::4326"), dx=1.05623e-07, dy=9.01846e-08)


##Export dense point cloud in WGS 84 UTM zone 12n
chunk.exportPoints("/home/jgillan/DATA2/products/1a_u6_highdensity.las", projection=Metashape.CoordinateSystem("EPSG::32612"))


