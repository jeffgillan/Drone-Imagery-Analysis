### 1. Establish work folder.
setwd("D:\\Projects\\BLMGILA\\Classifications_in_R\\v3Results")

imagefolder = "D:\\Projects\\BLMGILA\\Classifications_in_R\\FullAreaZones\\variables\\subset\\"
trainingfolder = "D:\\Projects\\BLMGILA\\Classifications_in_R\\FullAreaZones\\training\\v3"
resultsfile = "D:\\Projects\\BLMGILA\\Classifications_in_R\\v3Results\\CARTDecisionTreeResults_v3.txt"
resultsmatrix = "D:\\Projects\\BLMGILA\\Classifications_in_R\\v3Results\\CARTFinalSummary_v3.txt" 
resultsimage = "CARTClassifiedImage_v3"

### 2. Activate libraries. You may need to download and install the libraries if you have not already.
library(C50)
library(partykit)
library(Cubist)
library(mvtnorm)
library(raster)
library(shapefiles)
library(sp)
library(rgdal)
library(caret)
library(class)
library(e1071)
library(maptools)
library(randomForest)
library(doParallel) 
registerDoParallel(cores = 20)
library(snow)
library(xlsx)
library(gdata)

### 3. Read in and stack the raster data.

### Creates a list of files in a specific location. The path can be changed along with the pattern to select specific files.
imglist <- list.files(path = imagefolder, pattern='.tif$', full.names = TRUE)
n_images <-length(imglist)

### Stacks the image files listed in the previous command.
img <- stack(imglist)

### 4. Read in the training shapefiles.

### Looks in the designated work folder for shp files with a specific naming convention
train.files <- list.files(path = trainingfolder, pattern='.shp$', full.names = TRUE)

### 5. This section of code will extract values from the image data for each training points.

### Creates an empty object filled in the next step.
train.full <- NULL

### Starts timer.
ptm <- proc.time()
for (x in seq_along(train.files)) {
  ### Read in the a shapefile
  train.locations <- readShapeSpatial(train.files[x])
  ### Extract values from the rasters at the shapefile point locations.
  train.predictors <- extract(img, train.locations, df = TRUE)
  ### Combine the data from multiple polygons in the shapefile. If the data is in a point shapefile instead ofpolygons, skip this next line.
  #train.predictors <- as.data.frame(do.call(rbind,train.predictotrairs))
  ### Add a column for the class type and populate it. 
  
  numChar <- nchar(trainingfolder)+2
  
  train.by.class <- cbind(train.predictors, "types" = substr(train.files[x], numChar, nchar(train.files[x])-4))
  ### Combine the data with data from previous loops.
  train.full <- rbind(train.full, train.by.class)
}
### Stops timer.
proc.time() - ptm


write.xlsx(train.full, "train_studyarea_v3.xlsx")

### 6. Splits each class into training and validation. p = dictates the percentage of the split.
train.index <- createDataPartition(train.full$types, p = .5, list=FALSE ) #.5 means 50% goes to training

### 7. Separate training and validation data into separate files.
###Percentage of data dictated by the p value above goes here
train <- train.full[train.index,]
###The remaining  of data above goes here
test <- train.full[-train.index,]
###Separates the variables from the class names for the training data
Xtrain <- train[,2:n_images+1] #columns in table (click table in Environment data window; first column is ID, last column is classes = y)
Ytrain <- train[,n_images+2]
###Separates the variables from the class names for the test data
Xtest <- test[,2:n_images+1]
Ytest <- test[,n_images+2]

### 8. Training the c50 model with the training data
testmodel<- C5.0(Xtrain, Ytrain, trials = 10, control = C5.0Control(winnow=FALSE)) #trials = how many runs
###Display trees and accuracy of training data
summary(testmodel)
###Save model summary to a text file
write(capture.output(summary(testmodel)), resultsfile)

### 9.Use model to predict using the reserved test data
p <- predict.C5.0(testmodel, Xtest, type="class")
###Assess accuracy of prediction
confusionMatrix(p, Ytest)
###Save assessment test to text file
write(capture.output(confusionMatrix(p, Ytest)), resultsmatrix)

### Starts timer.
ptm <- proc.time()
#Predict classes on raster image
beginCluster(20)
#NAvalue(img) <- x
clusterR(img,raster::predict, args=list(model=testmodel),
         filename=resultsimage, format="HFA", datatype="INT1U" ,
         overwrite=TRUE, na.action=na.omit)
endCluster()
### Stops timer.
proc.time() - ptm
# 
# ###Variable importance
# importance_usage <- C5imp(testmodel, metric = "usage", pct = TRUE)
# importance_splits <- C5imp(testmodel, metric = "splits", pct = TRUE)
# importance_usage
# importance_splits
# 
# 
# #Visualize the decision trees
# plot(testmodel, trial = 1, subtree = NULL)



my_cols <- c("#00AFBB", "#E7B800", "#FC4E07")  
pairs(train.full[,c(10,45,49)], pch = 19,  cex = 0.5,
      col = my_cols[train.full$types],
      lower.panel=NULL)


