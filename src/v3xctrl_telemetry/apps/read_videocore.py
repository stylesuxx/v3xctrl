from v3xctrl_telemetry import VideoCoreTelemetry

vct = VideoCoreTelemetry()

vct.update()
state = vct.state()

print(state)
