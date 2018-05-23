import torch
import torch.nn as nn
from torch.autograd import Variable
from torchain._ext import my_lib
from torchain.functions import chain_loss
from torchain import io


def test_aten():
    t = torch.FloatTensor([[1.0, 2.0], [3.0, 4.0]])
    my_lib.my_lib_aten_cpu(t)
    if torch.cuda.is_available():
        t = torch.cuda.FloatTensor([[1.0, 2.0], [3.0, 4.0]])
        my_lib.my_lib_aten(t)
        print(t)
        t.mm(t)
        # t = torch.cuda.FloatTensor([[1.0, 2.0], [3.0, 4.0]])
        # my_lib.my_lib_aten(t)
        out = torch.cuda.FloatTensor([0])
        grads = torch.cuda.FloatTensor([0])
        my_lib.my_lib_test_chain(out, grads)
        print(out.shape, grads.shape)

def test_example():
    ffi = my_lib._my_lib.ffi
    def cstr(s):
        return ffi.new("char[]", s.encode())

    exp_root = "/data/work70/skarita/exp/chime5/kaldi-22fbdd/egs/chime5/s5/"
    den_fst_rs = exp_root + "exp/chain_train_worn_u100k_cleaned/tdnn1a_sp/den.fst"
    example_rs = "ark,bg:nnet3-chain-copy-egs --frame-shift=1  ark:" + exp_root + "exp/chain_train_worn_u100k_cleaned/tdnn1a_sp/egs/cegs.1.ark ark:- | nnet3-chain-shuffle-egs --buffer-size=5000 --srand=0 ark:- ark:- | nnet3-chain-merge-egs --minibatch-size=128,64,32 ark:- ark:- |"

    # FIXME: this is generated by the commands above
    my_lib.my_lib_set_kaldi_device(torch.cuda.FloatTensor(1))
    example_rs = "ark:/home/skarita/work/repos/extension-ffi-kaldi/package/mb.ark"

    # example_rs = "ark:cat tmp.ark |"

    example = my_lib.my_lib_example_reader_new(cstr(example_rs))
    supervision = my_lib.my_lib_supervision_new(example)
    n_pdf = my_lib.my_lib_supervision_num_pdf(supervision)
    n_seq = my_lib.my_lib_supervision_num_sequence(supervision)
    n_out_frame = my_lib.my_lib_supervision_num_frame(supervision)
    den_graph = my_lib.my_lib_denominator_graph_new(cstr(den_fst_rs), n_pdf)
    my_lib.my_lib_supervision_free(supervision)

    # TODO find what these options mean
    # relu-batchnorm-layer name=prefinal-chain l2-regularize=0.05 dim=512 target-rms=0.5
    # output-layer name=output include-log-softmax=false l2-regularize=0.01 bottleneck-dim=320 dim=2928 max-change=1.5

    model = torch.nn.Sequential(
        torch.nn.Conv1d(40, 512, 29, 3),
        torch.nn.ReLU(),
        torch.nn.Conv1d(512, n_pdf, 1, 1)
    )
    model.cuda()
    opt = torch.optim.SGD(model.parameters(), lr=1e-6)
    for i in range(20):
        # iter
        print("epoch", i)
        supervision = my_lib.my_lib_supervision_new(example)
        n_out_frame = my_lib.my_lib_supervision_num_frame(supervision)
        mfcc = torch.FloatTensor([0])
        ivec = torch.FloatTensor([0])
        n = my_lib.my_lib_example_feats(example, mfcc, ivec)
        assert n == 2, "number of inputs"
        n_batch, n_ivec = ivec.shape
        assert n_batch == n_seq
        n_input = mfcc.shape[1]
        mfcc = mfcc.view(n_batch, -1, n_input)
        n_in_frame = mfcc.shape[1]
        # forward
        x = Variable(mfcc.transpose(1, 2)).cuda()
        pred = model(x)
        pred = pred.transpose(1, 2).contiguous().view(-1, n_pdf)
        loss, results = chain_loss(pred, den_graph, supervision, l2_regularize=0.01)
        print(results)
        opt.zero_grad()
        loss.backward()
        opt.step()
        my_lib.my_lib_supervision_free(supervision)
        # if my_lib.my_lib_example_reader_next(example) == 0:
        #     break
    import matplotlib as mpl
    mpl.use('Agg')
    import matplotlib.pyplot as plt
    plt.matshow(mfcc[0])
    plt.savefig("test.png")
    my_lib.my_lib_denominator_graph_free(den_graph)
    my_lib.my_lib_example_reader_free(example)


def test_io():
    exp_root = "/data/work70/skarita/exp/chime5/kaldi-22fbdd/egs/chime5/s5/"
    den_fst_rs = exp_root + "exp/chain_train_worn_u100k_cleaned/tdnn1a_sp/den.fst"
    example_rs = "ark:/home/skarita/work/repos/extension-ffi-kaldi/package/mb.ark"
    # example_rs = "ark:cat tmp.ark |"

    io.set_kaldi_device()
    example = io.Example(example_rs)
    n_pdf = example.supervision.n_pdf
    print(n_pdf)
    den_graph = io.DenominatorGraph(den_fst_rs, n_pdf)
    model = torch.nn.Sequential(
        torch.nn.Conv1d(40, 512, 29, 3),
        torch.nn.ReLU(),
        torch.nn.Conv1d(512, n_pdf, 1, 1)
    )
    model.cuda()
    opt = torch.optim.SGD(model.parameters(), lr=1e-6)
    count = 0
    for (mfcc, ivec), supervision in io.Example(example_rs):
        x = Variable(mfcc).cuda()
        pred = model(x)
        loss, results = chain_loss(pred, den_graph, supervision, l2_regularize=0.01)
        opt.zero_grad()
        loss.backward()
        opt.step()
        print(count, results)
        count += 1
        if count > 20:
            break


if __name__ == "__main__":
    # test_aten()
    test_example()
    test_io()
    
