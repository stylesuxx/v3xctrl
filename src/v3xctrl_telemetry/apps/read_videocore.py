from v3xctrl_telemetry.VideoCoreTelemetry import VideoCoreTelemetry

vct = VideoCoreTelemetry()
vct.update()

state = vct.get_state()
print(state)
