def test_kernel_channels(client, authenticated_user):
    with client.websocket_connect(
        "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
        cookies=client.cookies,
    ):
        pass
