import unittest
import torch
from steering.core import ResidualSteerer, normalize_schedule, position_bin

class SteeringTests(unittest.TestCase):
    def test_interventions_leave_model_parameters_unchanged(self):
        layer=torch.nn.Linear(2,2,bias=False)
        original={k:v.clone() for k,v in layer.state_dict().items()}
        fit={'layers':[0],'residual_norms':torch.ones(1),'caa':torch.ones(1,2),
             'joint':torch.ones(1,4,2),'pooled':torch.ones(1,4,2),
             'sttp':{0:{'u':torch.tensor([1.,0.]),'t':100.,'mu_pos':5.,'sd_pos':3.}}}
        for condition in ['baseline','caa','sttp','rank2','pooled']:
            with self.subTest(condition=condition):
                with ResidualSteerer([layer],fit,condition,layer=0,strength=.1,c=2.) as hook:
                    hook.set_positions(torch.tensor([0]),1)
                    layer(torch.ones(1,1,2))
                self.assertTrue(all(torch.equal(value,layer.state_dict()[key]) for key,value in original.items()))
                self.assertEqual(len(layer._forward_hooks),0)
    def test_bins_and_budget(self):
        self.assertEqual([position_bin(k) for k in [0,1,3,4,11,12,100]], [0,1,1,2,2,3,3])
        raw=torch.arange(1,25,dtype=torch.float32).reshape(2,4,3)
        norms=torch.tensor([2.,7.])
        schedule=normalize_schedule(raw,norms)
        self.assertTrue(torch.allclose((schedule/norms[:,None,None]).square().sum((0,2)),torch.ones(4),atol=1e-6))

    def test_sttp_threshold_target_and_window(self):
        layers=[torch.nn.Identity()]
        fit={'layers':[0],'residual_norms':torch.tensor([10.]),'sttp':{0:{'u':torch.tensor([1.,0.]),'t':2.,'mu_pos':5.,'sd_pos':3.}}}
        x=torch.tensor([[[0.,7.],[1.,7.],[3.,7.]]])
        with ResidualSteerer(layers,fit,'sttp',layer=0,c=1.) as hook:
            hook.set_positions(torch.arange(3),2)
            y=layers[0](x)
            self.assertTrue(torch.equal(y,torch.tensor([[[0.,7.],[8.,7.],[3.,7.]]])))
            self.assertEqual(hook.stats()['fraction_eligible_steered'],.5)
        self.assertTrue(torch.equal(layers[0](x),x))

    def test_cached_bin_vectors_and_zero_strength(self):
        layers=[torch.nn.Identity()]
        schedule=torch.tensor([[[1.,0.],[0.,2.],[3.,0.],[0.,4.]]])
        fit={'layers':[0],'residual_norms':torch.tensor([1.]),'joint':schedule}
        x=torch.zeros(1,1,2)
        with ResidualSteerer(layers,fit,'rank2',strength=1.) as hook:
            for k in [0,1,3,4,11,12,20]:
                hook.set_positions(torch.tensor([9+k]),10)
                self.assertTrue(torch.equal(layers[0](x)[0,0],schedule[0,position_bin(k)]))
        with ResidualSteerer(layers,fit,'rank2',strength=0.) as hook:
            hook.set_positions(torch.tensor([9]),10)
            self.assertIs(layers[0](x),x)

if __name__=='__main__':unittest.main()
