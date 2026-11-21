from manipulation_tasks import ManipulationTrial,ROOT
from PIL import Image
import json
trial=ManipulationTrial('block',0)
def capture(t,phase):
    index=len(t.records)
    if index in (124,145,155,160,180,210,235):
        Image.fromarray(t.sim.rgb('overhead')).save(ROOT/f'grasp_debug_{index}.png')
        print(index,phase,t.records[-1],flush=True)
print(trial.run(callback=capture));trial.close()
