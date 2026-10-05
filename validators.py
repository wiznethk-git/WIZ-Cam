def validate_jpeg(data)
    print("SOI:", data.find(b'\xff\xd8'))
    print("EOI:", data.find(b'\xff\xd9'))

    print("DQT:", data.find(b'\xff\xdb'))
    print("SOF0:", data.find(b'\xff\xc0'))
    print("DHT:", data.find(b'\xff\xc4'))
    print("SOS:", data.find(b'\xff\xda'))
    print("length:", len(data))
