import unittest
import torch
from steering.cp_exploratory import CPReplayHook,bin3
from steering.core import normalize_schedule

class CPTests(unittest.TestCase):
    def test_cp_factorization_and_static_budget(self):
        torch.manual_seed(42)
        A=torch.randn(5,2);B=torch.randn(3,2);C=torch.randn(7,2)
        W=torch.einsum('lr,pr,hr->lph',A,B,C)
        direct=sum(A[:,r,None,None]*B[None,:,r,None]*C[None,None,:,r] for r in range(2))
        self.assertTrue(torch.allclose(W,direct,atol=1e-6))
        scales=torch.arange(1,6,dtype=torch.float32)
        scheduled=normalize_schedule(W,scales)
        static=normalize_schedule(W.mean(1,keepdim=True).expand(-1,3,-1).clone(),scales)
        for x in [scheduled,static]:self.assertTrue(torch.allclose((x/scales[:,None,None]).square().sum((0,2)),torch.ones(3),atol=1e-6))
        self.assertTrue(torch.equal(static[:,0],static[:,1]))
    def test_window_and_cached_bins(self):
        raw=torch.tensor([[[1.,0.],[0.,1.],[1.,1.]]]);schedule=torch.zeros(1,4,2);schedule[:,1:]=raw
        fit={'layers':[0],'residual_norms':torch.ones(1),'scheduled':schedule,'static':schedule}
        layer=torch.nn.Identity();x=torch.zeros(1,1,2)
        with CPReplayHook([layer],fit,condition='cp_scheduled',strength=1.) as hook:
            hook.set_positions(torch.tensor([9]),10)
            self.assertIs(layer(x),x)
            for offset in [1,3,4,11,12,100]:
                hook.set_positions(torch.tensor([9+offset]),10)
                self.assertTrue(torch.equal(layer(x)[0,0],raw[0,bin3(offset)]))
        with self.assertRaises(ValueError):bin3(0)
    def test_exact_zero(self):
        torch.manual_seed(42);layer=torch.nn.Identity();x=torch.randn(1,8,2,dtype=torch.bfloat16)
        fit={'layers':[0],'residual_norms':torch.ones(1),'scheduled':torch.randn(1,4,2),'static':torch.randn(1,4,2)}
        for mode in ['cp_scheduled','cp_static']:
            with CPReplayHook([layer],fit,condition=mode,strength=0.) as hook:
                hook.set_positions(torch.arange(8),3)
                self.assertIs(layer(x),x)

if __name__=='__main__':unittest.main()
