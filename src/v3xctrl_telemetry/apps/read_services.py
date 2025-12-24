from v3xctrl_telemetry.ServiceTelemetry import ServiceTelemetry

st = ServiceTelemetry()
st.update()

state = st.get_state()
print(state)
