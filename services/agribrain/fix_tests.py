import re
f = open('layer0/sensors/tests/test_engine.py','r')
c = f.read()
f.close()

c = re.sub(
    r'SensorCalibrationProfile\(profile_id="c1", sensor_family="generic", calibration_type="([a-z_]+)", variables=\["soil_moisture_vwc"\], valid_from=datetime.now\(\)\)',
    r'SensorCalibrationProfile(calibration_profile_id="c1", device_id="d1", variable="soil_moisture_vwc", calibration_type="\1", valid_from=datetime.now())',
    c
)
c = c.replace('"field_soil_specific"', '"soil_specific"')

f = open('layer0/sensors/tests/test_engine.py','w')
f.write(c)
f.close()
