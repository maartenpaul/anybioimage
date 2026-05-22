"""render_backend kwarg is accepted for one release with a DeprecationWarning."""
import warnings

from anybioimage import BioImageViewer


def test_deprecation_warning_on_render_backend():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        v = BioImageViewer(render_backend="viv")
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert v is not None


def test_default_construction_no_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        v = BioImageViewer()
        assert not any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert v is not None
