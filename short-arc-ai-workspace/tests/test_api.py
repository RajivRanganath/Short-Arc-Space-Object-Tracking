from fastapi.testclient import TestClient
from src.api.main import app
import datetime

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "tracks": 0}

def test_process_frame():
    # Construct a dummy frame request
    payload = {
        "timestamp_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "measurements": [
            {
                "site_eci": [6378.0, 0.0, 0.0],
                "range": 500.0,
                "ra": 0.1,
                "dec": 0.2,
                "true_object_id": 42
            }
        ]
    }
    
    response = client.post("/process_frame", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "timestamp" in data
    assert data["active_tracks"] == 1
    assert len(data["tracks"]) == 1
    
    track = data["tracks"][0]
    assert track["id"] == 0
    assert track["status"] == "LEO"
    assert track["quality_metric"] > 0

def test_websocket_endpoint():
    with client.websocket_connect("/ws") as websocket:
        # Check initial payload
        data = websocket.receive_json()
        assert "tracks" in data
        assert "stations" in data
        assert "phase" in data
        
        # Send start command
        websocket.send_json({
            "action": "start",
            "nObjects": 1,
            "duration": 5,
            "speed": 10,
            "method": "gnn"
        })
        
        # Receive the 'Initializing' payload
        data2 = websocket.receive_json()
        assert data2["simRunning"] is True
        
        # Send stop command
        websocket.send_json({
            "action": "stop"
        })
        
        # Receive stopped payload
        data3 = websocket.receive_json()
        assert data3["simRunning"] is False
