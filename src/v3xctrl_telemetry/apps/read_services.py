from v3xctrl_telemetry import ServiceTelemetry

st = ServiceTelemetry()
st.update()

state = st.state()

print(state)
