import unittest
import torch

from torch.testing import assert_close
from normflows import NormalizingFlow, ClassCondFlow, \
    NormalizingFlowVAE
from normflows.flows import MaskedAffineFlow
from normflows.nets import MLP
from normflows.distributions.base import DiagGaussian, \
    ClassCondDiagGaussian
from normflows.distributions.target import CircularGaussianMixture
from normflows.distributions.encoder import NNDiagGaussian
from normflows.distributions.decoder import NNDiagGaussianDecoder


class CoreTest(unittest.TestCase):
    def test_normalizing_flow(self):
        batch_size = 5
        latent_size = 2
        for n_layers in [2, 5]:
            with self.subTest(n_layers=n_layers):
                # Construct flow model
                layers = []
                for i in range(n_layers):
                    b = torch.Tensor([j if i % 2 == j % 2 else 0 for j in range(latent_size)])
                    s = MLP([latent_size, 2 * latent_size, latent_size], init_zeros=True)
                    t = MLP([latent_size, 2 * latent_size, latent_size], init_zeros=True)
                    layers.append(MaskedAffineFlow(b, t, s))
                base = DiagGaussian(latent_size)
                target = CircularGaussianMixture()
                model = NormalizingFlow(base, layers, target)
                # Test log prob and sampling
                inputs = torch.randn((batch_size, latent_size))
                log_q = model.log_prob(inputs)
                assert log_q.shape == (batch_size,)
                s, log_q = model.sample(batch_size)
                assert log_q.shape == (batch_size,)
                assert s.shape == (batch_size, latent_size)
                # Test losses
                loss = model.forward_kld(inputs)
                assert loss.dim() == 0
                loss = model.reverse_kld(batch_size)
                assert loss.dim() == 0
                loss = model.reverse_alpha_div(batch_size)
                assert loss.dim() == 0
                # Test forward and inverse
                outputs = model.forward(inputs)
                inputs_ = model.inverse(outputs)
                assert_close(inputs_, inputs)
                outputs, log_det = model.forward_and_log_det(inputs)
                inputs_, log_det_ = model.inverse_and_log_det(outputs)
                assert_close(inputs_, inputs)
                assert_close(log_det, -log_det_)

    def test_cc_normalizing_flow(self):
        batch_size = 5
        latent_size = 2
        n_layers = 2
        n_classes = 3

        # Construct flow model
        layers = []
        for i in range(n_layers):
            b = torch.Tensor([j if i % 2 == j % 2 else 0 for j in range(latent_size)])
            s = MLP([latent_size, 2 * latent_size, latent_size], init_zeros=True)
            t = MLP([latent_size, 2 * latent_size, latent_size], init_zeros=True)
            layers.append(MaskedAffineFlow(b, t, s))
        base = ClassCondDiagGaussian(latent_size, n_classes)
        model = ClassCondFlow(base, layers)

        # Test model
        x = torch.randn((batch_size, latent_size))
        y = torch.randint(n_classes, (batch_size,))
        log_q = model.log_prob(x, y)
        assert log_q.shape == (batch_size,)
        s, log_q = model.sample(x, y)
        assert log_q.shape == (batch_size,)
        assert s.shape == (batch_size, latent_size)
        loss = model.forward_kld(x, y)
        assert loss.dim() == 0

    def test_normalizing_flow_vae(self):
        batch_size = 5
        n_dim = 10
        n_layers = 2
        n_bottleneck = 3
        n_hidden_untis = 16
        hidden_units_encoder = [n_dim, n_hidden_untis, n_bottleneck * 2]
        hidden_units_decoder = [n_bottleneck, n_hidden_untis, 2 * n_dim]

        # Construct flow model
        layers = []
        for i in range(n_layers):
            b = torch.Tensor([j if i % 2 == j % 2 else 0 for j in range(n_bottleneck)])
            s = MLP([n_bottleneck, 2 * n_bottleneck, n_bottleneck], init_zeros=True)
            t = MLP([n_bottleneck, 2 * n_bottleneck, n_bottleneck], init_zeros=True)
            layers.append(MaskedAffineFlow(b, t, s))
        prior = torch.distributions.MultivariateNormal(torch.zeros(n_bottleneck),
                                                       torch.eye(n_bottleneck))
        encoder_nn = MLP(hidden_units_encoder)
        encoder = NNDiagGaussian(encoder_nn)
        decoder_nn = MLP(hidden_units_decoder)
        decoder = NNDiagGaussianDecoder(decoder_nn)
        model = NormalizingFlowVAE(prior, encoder, layers, decoder)

        # Test model
        for num_samples in [1, 4]:
            with self.subTest(num_samples=num_samples):
                x = torch.randn((batch_size, n_dim))
                z, log_p, log_q = model(x, num_samples=num_samples)
                assert z.shape == (batch_size, num_samples, n_bottleneck)
                assert log_p.shape == (batch_size, num_samples)
                assert log_q.shape == (batch_size, num_samples)


if __name__ == "__main__":
    unittest.main()