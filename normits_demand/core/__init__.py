# ## EXPOSE CORE OBJECTS ## #
from normits_demand.core.segments import SegmentationLevel
from normits_demand.core.zoning import ZoningSystem

from normits_demand.core.data_structures import DVector

# ## EXPOSE GETTER FUNCTIONS ## #
from normits_demand.core.zoning import get_zoning_system
from normits_demand.core.segments import get_segmentation_level

# ## EXPOSE USEFUL FUNCTIONALITY ## #
from normits_demand.core.data_structures import multiply_and_aggregate_dvectors
from normits_demand.core.data_structures import read_compressed_dvector
from normits_demand.core.data_structures import from_pickle

# ## EXPOSE ERRORS ## #
from normits_demand.core.zoning import ZoningError
from normits_demand.core.segments import SegmentationError
from normits_demand.core.data_structures import DVectorError