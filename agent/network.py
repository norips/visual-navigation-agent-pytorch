import torch
import torch.nn as nn
import torch.nn.functional as F


def compare_models(model_1, model_2):
    models_differ = 0
    for key_item_1, key_item_2 in zip(model_1.state_dict().items(), model_2.state_dict().items()):
        if torch.equal(key_item_1[1], key_item_2[1]):
            pass
        else:
            models_differ += 1
            if (key_item_1[0] == key_item_2[0]):
                print('Mismtach found at', key_item_1[0])
            else:
                raise Exception
    if models_differ == 0:
        print('Models match perfectly! :)')


class DQN(nn.Module):
    def __init__(self):
        super(DQN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=5, stride=2)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=2)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 32, kernel_size=5, stride=2)
        self.bn3 = nn.BatchNorm2d(32)
        self.head = nn.Linear(448, 2)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        return self.head(x.view(x.size(0), -1))


class SharedNetwork(nn.Module):
    def __init__(self, method, mask_size=5):
        super(SharedNetwork, self).__init__()
        self.method = method

        if self.method == 'word2vec':
            self.word_embedding_size = 300
            self.fc_target = nn.Linear(
                self.word_embedding_size, self.word_embedding_size)
            # Observation layer
            self.fc_observation = nn.Linear(8192, 512)

            # Convolution for similarity grid
            pooling_kernel = 2
            self.conv1 = nn.Conv2d(1, 8, 3, stride=1)
            self.pool = nn.MaxPool2d(pooling_kernel, pooling_kernel)
            self.conv2 = nn.Conv2d(8, 16, 5, stride=1)

            conv1_output = (mask_size - 3 + 1)//pooling_kernel
            conv2_output = (conv1_output - 5 + 1)//pooling_kernel
            self.flat_input = 16 * conv2_output * conv2_output

            # Merge layer
            self.fc_merge = nn.Linear(
                512+self.word_embedding_size+self.flat_input, 512)

        elif self.method == 'word2vec_noconv':
            self.word_embedding_size = 300
            self.fc_target = nn.Linear(
                self.word_embedding_size, self.word_embedding_size)
            # Observation layer
            self.fc_observation = nn.Linear(8192, 512)

            self.flat_input = mask_size * mask_size
            self.fc_similarity = nn.Linear(self.flat_input, self.flat_input)

            # Merge layer
            self.fc_merge = nn.Linear(
                512+self.word_embedding_size+self.flat_input, 512)

        elif self.method == "word2vec_nosimi":
            self.word_embedding_size = 300
            self.fc_target = nn.Linear(
                self.word_embedding_size, self.word_embedding_size)
            # Observation layer
            self.fc_observation = nn.Linear(8192, 512)
            self.fc_merge = nn.Linear(self.word_embedding_size + 512, 512)
        elif self.method == 'aop':
            # Target object layer
            self.fc_target = nn.Linear(2048, 512)

            # Observation layer
            self.fc_observation = nn.Linear(8192, 512)

            # Merge layer
            self.fc_merge = nn.Linear(1024+(mask_size*mask_size), 512)
        elif self.method == 'target_driven':
            # Siemense layer
            self.fc_siemense = nn.Linear(8192, 512)

            # Merge layer
            self.fc_merge = nn.Linear(1024, 512)
        else:
            raise Exception("Please choose a method")

    def forward(self, inp):
        if self.method == 'word2vec':
            # x is the observation
            # y is the target
            # z is the object location mask
            (x, y, z) = inp

            x = x.view(-1)
            x = self.fc_observation(x)
            x = F.relu(x, True)

            y = y.view(-1)
            y = self.fc_target(y)
            y = F.relu(y, True)

            z = self.pool(F.relu(self.conv1(z)))
            z = self.pool(F.relu(self.conv2(z)))
            z = z.view(-1)

            # xy = torch.stack([x, y], 0).view(-1)
            xyz = torch.cat([x, y, z])
            xyz = self.fc_merge(xyz)
            xyz = F.relu(xyz, True)
            return xyz

        elif self.method == 'word2vec_noconv':
            # x is the observation
            # y is the target
            # z is the object location mask
            (x, y, z) = inp

            x = x.view(-1)
            x = self.fc_observation(x)
            x = F.relu(x, True)

            y = y.view(-1)
            y = self.fc_target(y)
            y = F.relu(y, True)

            z = z.view(-1)
            z = self.fc_similarity(z)
            z = F.relu(z, True)

            # xy = torch.stack([x, y], 0).view(-1)
            xyz = torch.cat([x, y, z])
            xyz = self.fc_merge(xyz)
            xyz = F.relu(xyz, True)
            return xyz

        elif self.method == 'word2vec_nosimi':
            # x is the observation
            # y is the target
            (x, y) = inp

            x = x.view(-1)
            x = self.fc_observation(x)
            x = F.relu(x, True)

            y = y.view(-1)
            y = self.fc_target(y)
            y = F.relu(y, True)

            xy = torch.cat([x, y])
            xy = self.fc_merge(xy)
            xy = F.relu(xy, True)
            return xy
        elif self.method == 'aop':
            # x is the observation
            # y is the target
            # z is the object location mask
            (x, y, z) = inp

            x = x.view(-1)
            x = self.fc_observation(x)
            x = F.relu(x, True)

            y = y.view(-1)
            y = self.fc_target(y)
            y = F.relu(y, True)

            z = z.view(-1)

            xy = torch.stack([x, y], 0).view(-1)
            xyz = torch.cat([xy, z])
            xyz = self.fc_merge(xyz)
            xyz = F.relu(xyz, True)
            return xyz
        elif self.method == 'target_driven':
            (x, y,) = inp

            x = x.view(-1)
            x = self.fc_siemense(x)
            x = F.relu(x, True)

            y = y.view(-1)
            y = self.fc_siemense(y)
            y = F.relu(y, True)

            xy = torch.stack([x, y], 0).view(-1)
            xy = self.fc_merge(xy)
            xy = F.relu(xy, True)
            return xy


class SceneSpecificNetwork(nn.Module):
    """
    Input for this network is 512 tensor
    """

    def __init__(self, action_space_size):
        super(SceneSpecificNetwork, self).__init__()
        self.fc1 = nn.Linear(512, 512)

        # Policy layer
        self.fc2_policy = nn.Linear(512, action_space_size)

        # Value layer
        self.fc2_value = nn.Linear(512, 1)

    def forward(self, x):
        x = self.fc1(x)
        x = F.relu(x)
        x_policy = self.fc2_policy(x)
        # x_policy = F.softmax(x_policy)

        x_value = self.fc2_value(x)[0]
        return (x_policy, x_value, )


class ActorCriticLoss(nn.Module):
    def __init__(self, entropy_beta):
        self.entropy_beta = entropy_beta

    def forward(self, policy, value, action_taken, temporary_difference, r):
        # Calculate policy entropy
        log_softmax_policy = torch.nn.functional.log_softmax(policy, dim=1)
        softmax_policy = torch.nn.functional.softmax(policy, dim=1)
        policy_entropy = softmax_policy * log_softmax_policy
        policy_entropy = -torch.sum(policy_entropy, 1)

        # Policy loss
        nllLoss = F.nll_loss(log_softmax_policy, action_taken, reduce=False)
        policy_loss = nllLoss * temporary_difference - policy_entropy * self.entropy_beta
        policy_loss = policy_loss.sum(0)

        # Value loss
        # learning rate for critic is half of actor's
        # Equivalent to 0.5 * l2 loss
        value_loss = (0.5 * 0.5) * F.mse_loss(value, r, size_average=False)
        return value_loss + policy_loss
