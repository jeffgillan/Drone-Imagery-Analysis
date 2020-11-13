###Supplemental 2. Script to generate vegetation height model by subtracting digital terrain model from digital surface model. Rstudio 1.0.153 


setwd("F:\\yourworkspace\\yourworkspace")

library(raster)
library(sp)

#Let's leverage most of the local computing resources to speed up the process. '31' is the number of logical processors
beginCluster(31, type = 'SOCK')

#import the DSM and DTM from the working directory
DSM = raster("My_DSM.tif")
DTM = raster("My_DTM.tif")

#Stack DSM and DTM together
DEMstack = stack(DSM, DTM)

#subtract on a cell-by-cell basis the DTM (y) from the DSM (x)
VHM = clusterR(DEMstack, overlay, args=list(fun=function(x,y){return(x-y)}))

#Remove any heights less than 5 cm. Most of this probably error.
VHM_clean <- calc(VHM, function(i){ i[i<0.05] <- 0; i})

#Export the VHM out to a .tif in the working directory
writeRaster(VHM_clean, filename="LH_007_CHM.tif", format="GTiff", datatype='FLT4S', overwrite=TRUE)
endCluster()