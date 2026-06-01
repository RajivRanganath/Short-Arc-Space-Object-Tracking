from src.simulation.multi_object_scenarios import ScenarioGenerator

def test_furball():
    print("========================================")
    print("🌪️  TEST: DEBRIS CLOUD GENERATION")
    print("========================================")
    
    gen = ScenarioGenerator()
    
    # Generate a cloud of 5 objects over 30 seconds
    measurements, truth = gen.generate_scenario(n_objects=5, duration_sec=30)
    
    # Validation
    print("\n🔍 INSPECTING DATA STREAM:")
    
    # Print first 10 measurements
    for i, m in enumerate(measurements[:10]):
        print(f"   T={m['time']}s | RA={m['ra']:.4f} | Dec={m['dec']:.4f} | Truth_ID={m['true_object_id']}")
        
    unique_ids = set(m['true_object_id'] for m in measurements)
    print(f"\n📊 Unique Objects in Stream: {len(unique_ids)}")
    
    if len(unique_ids) == 5:
        print("✅ SUCCESS: 5 distinct objects simulated simultaneously.")
    else:
        print("❌ FAILURE: Object count mismatch.")

if __name__ == "__main__":
    test_furball()
