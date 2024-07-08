"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsFeatureSink,
    QgsRasterLayer,
    QgsRasterFileWriter,
    QgsProcessingException,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber
)
from qgis.analysis import (
    QgsRasterCalculator,
    QgsRasterCalculatorEntry
)
from qgis import processing
import os
import math

class LSTProcessingAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    OUTPUT_RIFL_4 = 'OUTPUT_RIFL_4.tif'
    OUTPUT_RIFL_5 = 'OUTPUT_RIFL_5.tif'
    OUTPUT_E = 'OUTPUT_E.tif'
    OUTPUT_TOA_BRIGHTNESS = 'OUTPUT_TOA_BRIGHTNESS.tif'
    OUTPUT_LST = 'OUTPUT_LST.tif'
    RASTER_PATH = ''
    NDVImax = 'NDVImax'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return LSTProcessingAlgorithm()

    def name(self):
        return 'calculate_LST'

    def displayName(self):
        return self.tr('Calculate the land surface temperature')

    def group(self):
        return self.tr('Raster tools')

    def groupId(self):
        return 'rastertools'

    def shortHelpString(self):
        return self.tr("Loads from a folder three raster layers from landsat 8-9 (L1 bands 4,5 and 10) and calculates Land Surface Temperature")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.RASTER_PATH,
                self.tr('Raster Images Path'),
                optional=False,
                behavior=QgsProcessingParameterFile.Behavior.Folder
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NDVImax,
                self.tr('NDVI max'),
                type=QgsProcessingParameterNumber.Double,
                minValue=0.5,
                maxValue=0.8,
                defaultValue=0.6
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def extract_value(self, key, content):
        start = content.find(key) + len(key) + 3
        end = content.find("\n", start)
        return content[start:end].strip()

    def processAlgorithm(self, parameters, context, feedback):
        raster_path = self.parameterAsString(parameters, self.RASTER_PATH, context)
        ndvi_max = self.parameterAsDouble(parameters, self.NDVImax, context)

        mtl_file = next((f for f in os.listdir(raster_path) if f.endswith("MTL.txt")), None)
        
        if mtl_file:
            mtl_path = os.path.join(raster_path, mtl_file)
            with open(mtl_path, "r") as f:
                mtl_content = f.read()
                            
            file_name_band_4 = self.extract_value("FILE_NAME_BAND_4", mtl_content).strip('"')
            file_name_band_5 = self.extract_value("FILE_NAME_BAND_5", mtl_content).strip('"')
            file_name_band_10 = self.extract_value("FILE_NAME_BAND_10", mtl_content).strip('"')
            sun_elevation = float(self.extract_value("SUN_ELEVATION", mtl_content))
            reflectance_mult_band_4 = float(self.extract_value("REFLECTANCE_MULT_BAND_4", mtl_content))
            reflectance_mult_band_5 = float(self.extract_value("REFLECTANCE_MULT_BAND_5", mtl_content))
            reflectance_add_band_4 = float(self.extract_value("REFLECTANCE_ADD_BAND_4", mtl_content))
            reflectance_add_band_5 = float(self.extract_value("REFLECTANCE_ADD_BAND_5", mtl_content))
            radiance_mult_band_10 = float(self.extract_value("RADIANCE_MULT_BAND_10", mtl_content))
            radiance_add_band_10 = float(self.extract_value("RADIANCE_ADD_BAND_10", mtl_content))
            k1_constant_band_10 = float(self.extract_value("K1_CONSTANT_BAND_10", mtl_content))
            k2_constant_band_10 = float(self.extract_value("K2_CONSTANT_BAND_10", mtl_content))
        else:
            raise QgsProcessingException("MTL file not found in the specified directory.")

        b4_layer = QgsRasterLayer(os.path.join(raster_path, file_name_band_4), "B4") if file_name_band_4 else None
        b5_layer = QgsRasterLayer(os.path.join(raster_path, file_name_band_5), "B5") if file_name_band_5 else None
        b10_layer = QgsRasterLayer(os.path.join(raster_path, file_name_band_10), "B10") if file_name_band_10 else None

        if not b4_layer.isValid():
            raise QgsProcessingException(f"Failed to load raster layer B4 from {os.path.join(raster_path, file_name_band_4)}")
        if not b5_layer.isValid():
            raise QgsProcessingException(f"Failed to load raster layer B5 from {os.path.join(raster_path, file_name_band_5)}")
        if not b10_layer.isValid():
            raise QgsProcessingException(f"Failed to load raster layer B10 from {os.path.join(raster_path, file_name_band_10)}")

        entry_b4 = QgsRasterCalculatorEntry()
        entry_b4.ref = "b4@1"
        entry_b4.raster = b4_layer
        entry_b4.bandNumber = 1
        
        rifl_4_expression = f"(('b4@1' * {reflectance_mult_band_4}) - {reflectance_add_band_4}) / sin({sun_elevation})"
        output_path_rifl_4 = os.path.join(raster_path, self.OUTPUT_RIFL_4)
        calculator_rifl_4 = QgsRasterCalculator(rifl_4_expression,
                                               output_path_rifl_4,
                                               "GTiff",
                                               b4_layer.extent(),
                                               b4_layer.width(),
                                               b4_layer.height(),
                                               [entry_b4])
        calculator_rifl_4.processCalculation()
        
        entry_b5 = QgsRasterCalculatorEntry()
        entry_b5.ref = "b5@1"
        entry_b5.raster = b5_layer
        entry_b5.bandNumber = 1

        rifl_5_expression = f"(('b5@1' * {reflectance_mult_band_5}) - {reflectance_add_band_5}) / sin({sun_elevation})"
        output_path_rifl_5 = os.path.join(raster_path, self.OUTPUT_RIFL_5)
        calculator_rifl_5 = QgsRasterCalculator(rifl_5_expression,
                                               output_path_rifl_5,
                                               "GTiff",
                                               b5_layer.extent(),
                                               b5_layer.width(),
                                               b5_layer.height(),
                                               [entry_b5])
        calculator_rifl_5.processCalculation()
        
        NDVImin = 0.2

        e_expression = f"0.986 + 0.004 * ((('entry_rifl_5@1' - 'entry_rifl_4@1') / ('entry_rifl_5@1' + 'entry_rifl_4@1') - {NDVImin} ) / ( {ndvi_max} - {NDVImin}))"
        output_path_e = os.path.join(raster_path, self.OUTPUT_E)
        
        # Create QgsRasterCalculatorEntry objects for the previous RIFL_4 and RIFL_5 outputs
        output_layer_4 = QgsRasterLayer(output_path_rifl_4)
        output_layer_5 = QgsRasterLayer(output_path_rifl_5)
        
        entry_rifl_4 = QgsRasterCalculatorEntry()
        entry_rifl_4.ref = "entry_rifl_4@1"
        entry_rifl_4.raster = output_layer_4
        entry_rifl_4.bandNumber = 1
        entry_rifl_5 = QgsRasterCalculatorEntry()
        entry_rifl_5.ref = "entry_rifl_5@1"
        entry_rifl_5.raster = output_layer_5
        entry_rifl_5.bandNumber = 1
        
        calculator_e = QgsRasterCalculator(e_expression,
                                              output_path_e,
                                              "GTiff",
                                              b4_layer.extent(),
                                              b4_layer.width(),
                                              b4_layer.height(),
                                              [entry_rifl_4, entry_rifl_5])
        calculator_e.processCalculation()
        
        output_layer_emissivity = QgsRasterLayer(output_path_e)
        
        entry_layer_emissivity = QgsRasterCalculatorEntry()
        entry_layer_emissivity.ref = "entry_layer_emissivity@1"
        entry_layer_emissivity.raster = output_layer_emissivity
        entry_layer_emissivity.bandNumber = 1

        entry_b10 = QgsRasterCalculatorEntry()
        entry_b10.ref = "b10@1"
        entry_b10.raster = b10_layer
        entry_b10.bandNumber = 1
        
        toa_brightness_expression = f"({k2_constant_band_10} / (ln(({k1_constant_band_10} / (('b10@1' * {radiance_mult_band_10}) + {radiance_add_band_10})) + 1))) - 273.15"
        output_path_toa_brightness = os.path.join(raster_path, self.OUTPUT_TOA_BRIGHTNESS)
        calculator_toa_brightness = QgsRasterCalculator(toa_brightness_expression,
                                                        output_path_toa_brightness,
                                                        "GTiff",
                                                        b10_layer.extent(),
                                                        b10_layer.width(),
                                                        b10_layer.height(),
                                                        [entry_b10])
        calculator_toa_brightness.processCalculation()
        
        output_toa_brightness = QgsRasterLayer(output_path_toa_brightness)
        
        entry_toa_brightness = QgsRasterCalculatorEntry()
        entry_toa_brightness.ref = "entry_toa_brightness@1"
        entry_toa_brightness.raster = output_toa_brightness
        entry_toa_brightness.bandNumber = 1
        
        lst_expression = f"('entry_toa_brightness@1') / (1 + ((10.895 * 'entry_toa_brightness@1' / 14388) * ln('entry_layer_emissivity@1')))"
        output_lst = os.path.join(raster_path, self.OUTPUT_LST)
        calculator_lst = QgsRasterCalculator(lst_expression,
                                             output_lst,
                                             "GTiff",
                                             b10_layer.extent(),
                                             b10_layer.width(),
                                             b10_layer.height(),
                                             [entry_layer_emissivity, entry_toa_brightness])
        result_lst = calculator_lst.processCalculation()
        os.remove(output_path_rifl_4)
        os.remove(output_path_rifl_5)
        os.remove(output_path_e)
        os.remove(output_path_toa_brightness)
        
        return {self.OUTPUT: result_lst}


  
