"""Debug spots full pipeline."""
from services.agribrain.layer0.perception.farmer_photo.benchmark.cases import BENCHMARK_CASES
from services.agribrain.layer0.perception.farmer_photo.benchmark.run_benchmark import _generate_synthetic_pixels
from services.agribrain.layer0.perception.farmer_photo.preprocess import FarmerPhotoPreprocessor
from services.agribrain.layer0.perception.farmer_photo.symptom_classifier import SymptomClassifier

prep = FarmerPhotoPreprocessor()
symptom_cls = SymptomClassifier()

for case_id in ['symptom_spots', 'symptom_insect_maize']:
    for case in BENCHMARK_CASES:
        if case.case_id == case_id:
            pixels = _generate_synthetic_pixels(case)
            features = prep.preprocess("mock_bench_%s.jpg" % case_id, synthetic_pixels=pixels)
            
            scores = symptom_cls._compute_symptom_scores(features, "leaf")
            
            # Before normalization
            total = sum(scores.values())
            norm_scores = {k: v / total for k, v in scores.items()} if total > 0 else scores
            primary = max(norm_scores, key=norm_scores.get)
            
            print("=== %s ===" % case_id)
            print("  bstd=%.1f bright=%.1f rel_std=%.3f entropy=%.2f green_r=%.3f" % (
                features.brightness_std, features.brightness_mean,
                features.brightness_std / max(features.brightness_mean, 1),
                features.color_entropy, features.green_ratio))
            print("  Raw scores:")
            for sym, sc in sorted(scores.items(), key=lambda x: -x[1])[:5]:
                print("    %s: %.3f -> norm %.3f" % (sym, sc, norm_scores[sym]))
            print("  Primary: %s (norm=%.3f)" % (primary, norm_scores[primary]))
            break
