from typing import Tuple
import torch.optim as optim
from src.ai.variants.blocks import ResidualBlockSmallBatchNorm, _make_layer_no_batchnorm_leaky
from src.navigation_core import BaseAutoencoderModel
from src.navigation_core import ROTATIONS_PER_FULL, OFFSETS_PER_DATAPOINT
from src.modules.save_load_handlers.parameters import *
from src.ai.runtime_storages.storage_superset2 import StorageSuperset2
from src.utils import array_to_tensor, get_device
from src.utils.pretty_display import pretty_display_reset, pretty_display_start, pretty_display, pretty_display_set
import torch
import torch.nn as nn


class AbstractionBlockImage(BaseAutoencoderModel):
    def __init__(self, dropout_rate: float = 0.2, position_embedding_size: int = 256, thetas_embedding_size: int = 256,
                 hidden_size: int = 1024, num_blocks: int = 2, input_output_size=512,
                 concatenated_instances: int = ROTATIONS_PER_FULL):
        super(AbstractionBlockImage, self).__init__()

        self.concatenated_instances = concatenated_instances
        input_output_size *= concatenated_instances
        self.input_layer = nn.Linear(input_output_size, hidden_size)
        self.encoding_blocks = nn.ModuleList(
            [ResidualBlockSmallBatchNorm(hidden_size, dropout_rate) for _ in range(num_blocks)])

        self.positional_encoder = _make_layer_no_batchnorm_leaky(hidden_size, position_embedding_size)
        self.thetas_encoder = _make_layer_no_batchnorm_leaky(hidden_size, thetas_embedding_size)

        self.decoder_initial_layer = _make_layer_no_batchnorm_leaky(position_embedding_size + thetas_embedding_size,
                                                                    hidden_size)
        self.decoding_blocks = nn.ModuleList(
            [ResidualBlockSmallBatchNorm(hidden_size, dropout_rate) for _ in range(num_blocks)])

        self.output_layer = nn.Linear(hidden_size, input_output_size)
        self.leaky_relu = nn.LeakyReLU()
        self.embedding_size = position_embedding_size

    def encoder_training(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:

        # Feedforward through the network
        x = self.input_layer(x)
        x = self.leaky_relu(x)

        for block in self.encoding_blocks:
            x = block(x)

        position = self.positional_encoder(x)
        thetas = self.thetas_encoder(x)

        return position, thetas

    def encoder_inference(self, x: torch.Tensor) -> torch.Tensor:
        position, _ = self.encoder_training(x)
        return position

    def decoder_training(self, positional_encoding, rotational_encoding) -> torch.Tensor:
        x = torch.cat([positional_encoding, rotational_encoding], dim=-1)
        x = self.decoder_initial_layer(x)
        x = self.leaky_relu(x)

        for block in self.decoding_blocks:
            x = block(x)

        x = self.output_layer(x)

        # Reshape the output back to the original shape
        # batch_size = x.shape[0]
        # x = x.view(batch_size, self.concatenated_instances, -1)

        return x

    def decoder_inference(self, positional_encoding, rotational_encoding) -> torch.Tensor:
        return self.decoder_training(positional_encoding, rotational_encoding)

    def forward_training(self, x: torch.Tensor) -> torch.Tensor:
        positional_encoding, rotational_encoding = self.encoder_training(x)
        return self.decoder_training(positional_encoding, rotational_encoding)

    def forward_inference(self, x: torch.Tensor) -> torch.Tensor:
        return self.forward_training(x)

    def get_embedding_size(self) -> int:
        return self.embedding_size


_cache_reconstruction_loss = {}


def shuffle_tensor_dim1(tensor):
    dim1_size = tensor.size(1)
    indices = torch.randperm(dim1_size)
    shuffled_tensor = tensor[:, indices]
    return shuffled_tensor


def reconstruction_handling_with_freezing(autoencoder: BaseAutoencoderModel, storage: StorageSuperset2) -> any:
    global _cache_reconstruction_loss
    sampled_count = 100
    sampled_points = storage.sample_n_random_datapoints(sampled_count)
    data = []

    loss_reconstruction = torch.tensor(0.0, device=get_device())
    position_encoding_change_on_position = torch.tensor(0.0, device=get_device())
    position_encoding_change_on_rotation = torch.tensor(0.0, device=get_device())

    rotation_encoding_change_on_position = torch.tensor(0.0, device=get_device())
    rotation_encoding_change_on_rotation = torch.tensor(0.0, device=get_device())

    ratio_loss_position = torch.tensor(0.0, device=get_device())
    ratio_loss_rotation = torch.tensor(0.0, device=get_device())

    for point in sampled_points:
        point_data_arr = []
        if point in _cache_reconstruction_loss:
            point_data_arr = _cache_reconstruction_loss[point]
        else:
            # creates list of inputs for that point
            for i in range(OFFSETS_PER_DATAPOINT):
                sampled_full_rotation = array_to_tensor(
                    storage.get_point_rotations_with_full_info_set_offset_concatenated(point, ROTATIONS_PER_FULL, i))
                point_data_arr.append(sampled_full_rotation)

            _cache_reconstruction_loss[point] = point_data_arr
        data.extend(point_data_arr)

    data = torch.stack(data).to(device=get_device())
    positional_encoding, thetas_encoding = autoencoder.encoder_training(data)
    dec = autoencoder.decoder_training(positional_encoding, thetas_encoding)

    criterion_reconstruction = nn.MSELoss()
    loss_reconstruction = criterion_reconstruction(dec, data)
    # traverses each OFFSET_PER_DATAPOINT batch, selects tensors from each batch and calculates the loss

    positional_enc_arr = []
    rotational_enc_arr = []
    for i in range(sampled_count):
        start_index = i * OFFSETS_PER_DATAPOINT
        end_index = (i + 1) * OFFSETS_PER_DATAPOINT
        positional_encs = positional_encoding[start_index:end_index]
        rotational_encs = thetas_encoding[start_index:end_index]

        positional_enc_arr.append(positional_encs)
        rotational_enc_arr.append(rotational_encs)

    positional_enc_arr = torch.stack(positional_enc_arr)
    rotational_enc_arr = torch.stack(rotational_enc_arr)

    position_encoding_change_on_rotation = torch.cdist(positional_enc_arr, positional_enc_arr).mean()
    rotation_encoding_change_on_rotation = torch.cdist(rotational_enc_arr, rotational_enc_arr).mean()

    rotation_constant_array_rotation_embeddings = []
    rotation_constant_array_position_embeddings = []

    # putting same rotations in a list one after another
    for rotation_offset in range(OFFSETS_PER_DATAPOINT):
        for position_index in range(sampled_count):
            idx = position_index * OFFSETS_PER_DATAPOINT + rotation_offset
            rotation_constant_array_rotation_embeddings.append(thetas_encoding[idx])
            rotation_constant_array_position_embeddings.append(positional_encoding[idx])

    rotation_constant_array_rotation_embeddings = torch.stack(rotation_constant_array_rotation_embeddings).to(
        device=get_device())
    rotation_constant_array_position_embeddings = torch.stack(rotation_constant_array_position_embeddings).to(
        device=get_device()
    )

    positional_enc_arr = []
    rotational_enc_arr = []

    # position changes, rotation stays the same
    for i in range(OFFSETS_PER_DATAPOINT):
        start_index = i * sampled_count
        end_index = (i + 1) * sampled_count

        rotational_encs = rotation_constant_array_rotation_embeddings[start_index:end_index]
        positional_encs = rotation_constant_array_position_embeddings[start_index:end_index]

        positional_enc_arr.append(positional_encs)
        rotational_enc_arr.append(rotational_encs)

    positional_enc_arr = torch.stack(positional_enc_arr)
    rotational_enc_arr = torch.stack(rotational_enc_arr)

    position_encoding_change_on_position = torch.cdist(positional_enc_arr, positional_enc_arr).mean()
    rotation_encoding_change_on_position = torch.cdist(rotational_enc_arr, rotational_enc_arr).mean()

    ratio_loss_position = position_encoding_change_on_rotation / position_encoding_change_on_position
    ratio_loss_rotation = rotation_encoding_change_on_position / rotation_encoding_change_on_rotation

    return {
        "loss_reconstruction": loss_reconstruction,
        "ratio_loss_position": ratio_loss_position,
        "ratio_loss_rotation": ratio_loss_rotation,
        "rotation_encoding_change_on_position": rotation_encoding_change_on_position,
        "rotation_encoding_change_on_rotation": rotation_encoding_change_on_rotation,
        "position_encoding_change_on_position": position_encoding_change_on_position,
        "position_encoding_change_on_rotation": position_encoding_change_on_rotation
    }


def linearity_distance_handling(autoencoder: BaseAutoencoderModel, storage: StorageSuperset2,
                                non_adjacent_sample_size: int,
                                scale_non_adjacent_distance_loss: float, distance_per_neuron: float) -> torch.Tensor:
    """
    Makes first degree connections be linearly distant from each other
    """
    # sampled_pairs = storage.sample_datapoints_adjacencies(non_adjacent_sample_size)
    non_adjacent_sample_size = min(non_adjacent_sample_size, len(storage.get_all_connections_data()))
    sampled_pairs = storage.connections_authentic_sample(non_adjacent_sample_size)

    batch_datapoint1 = []
    batch_datapoint2 = []

    for pair in sampled_pairs:
        datapoint1 = storage.get_datapoint_data_tensor_by_name_permuted(pair["start"])
        datapoint2 = storage.get_datapoint_data_tensor_by_name_permuted(pair["end"])

        batch_datapoint1.append(datapoint1)
        batch_datapoint2.append(datapoint2)

    batch_datapoint1 = torch.stack(batch_datapoint1).to(get_device())
    batch_datapoint2 = torch.stack(batch_datapoint2).to(get_device())

    encoded_i, thetas_i = autoencoder.encoder_training(batch_datapoint1)
    encoded_j, thetas_j = autoencoder.encoder_training(batch_datapoint2)

    embedding_size = encoded_i.shape[1]

    distance = torch.norm(encoded_i - encoded_j, p=2, dim=1)
    expected_distance = [pair["distance"] for pair in sampled_pairs]
    expected_distance = torch.tensor(expected_distance, dtype=torch.float32).to(get_device())

    criterion = nn.MSELoss()

    non_adjacent_distance_loss = criterion(distance, expected_distance) * scale_non_adjacent_distance_loss
    return non_adjacent_distance_loss


def _train_autoencoder_abstraction_block(abstraction_block: AbstractionBlockImage, storage: StorageSuperset2,
                                         epochs: int,
                                         pretty_print: bool = False) -> AbstractionBlockImage:
    # PARAMETERS
    optimizer = optim.Adam(abstraction_block.parameters(), lr=0.00015, amsgrad=True)
    abstraction_block = abstraction_block.to(device=get_device())

    num_epochs = epochs
    scale_reconstruction_loss = 2
    scale_ratio_loss = 1.5
    scale_linearity_loss = 1

    epoch_average_loss = 0
    linearity_sample_size = 100
    DISTANCE_PER_NEURON = 0.005

    loss_same_position_average_loss = 0
    loss_same_rotation_average_loss = 0
    loss_ratio_position_average_loss = 0
    loss_ratio_rotation_average_loss = 0
    loss_linearity_average_loss = 0

    reconstruction_average_loss = 0

    epoch_print_rate = 250

    if pretty_print:
        pretty_display_set(epoch_print_rate, "Epoch batch")
        pretty_display_start(0)

    rotation_encoding_change_on_position_avg = 0
    rotation_encoding_change_on_rotation_avg = 0

    position_encoding_change_on_position_avg = 0
    position_encoding_change_on_rotation_avg = 0

    SHUFFLE = 5
    for epoch in range(num_epochs):
        if epoch % SHUFFLE == 0:
            storage.build_permuted_data_random_rotations()

        epoch_loss = 0.0
        optimizer.zero_grad()

        # RECONSTRUCTION LOSS
        losses_json = reconstruction_handling_with_freezing(
            abstraction_block,
            storage)
        linearity_loss = linearity_distance_handling(abstraction_block, storage, linearity_sample_size,
                                                     scale_linearity_loss, DISTANCE_PER_NEURON)

        reconstruction_loss = losses_json["loss_reconstruction"]

        ratio_loss_position = losses_json["ratio_loss_position"]
        ratio_loss_rotation = losses_json["ratio_loss_rotation"]
        rotation_encoding_change_on_position = losses_json["rotation_encoding_change_on_position"]
        rotation_encoding_change_on_rotation = losses_json["rotation_encoding_change_on_rotation"]
        position_encoding_change_on_position = losses_json["position_encoding_change_on_position"]
        position_encoding_change_on_rotation = losses_json["position_encoding_change_on_rotation"]

        reconstruction_loss *= scale_reconstruction_loss
        ratio_loss_position *= scale_ratio_loss
        ratio_loss_rotation *= scale_ratio_loss
        linearity_loss *= scale_linearity_loss

        reconstruction_loss.backward(retain_graph=True)
        linearity_loss.backward()

        position_encoding_change_on_rotation.backward(retain_graph=True)
        rotation_encoding_change_on_position.backward(retain_graph=True)

        ratio_loss_rotation.backward(retain_graph=True)
        ratio_loss_position.backward()

        optimizer.step()

        reconstruction_loss /= scale_reconstruction_loss
        ratio_loss_position /= scale_ratio_loss
        ratio_loss_rotation /= scale_ratio_loss
        linearity_loss /= scale_linearity_loss

        epoch_loss += reconstruction_loss.item() + position_encoding_change_on_rotation.item() + rotation_encoding_change_on_position.item() + ratio_loss_position.item() + ratio_loss_rotation.item() + linearity_loss.item()
        epoch_average_loss += epoch_loss

        reconstruction_average_loss += reconstruction_loss.item()
        loss_same_position_average_loss += position_encoding_change_on_rotation.item()
        loss_same_rotation_average_loss += rotation_encoding_change_on_position.item()
        loss_ratio_position_average_loss += ratio_loss_position.item()
        loss_ratio_rotation_average_loss += ratio_loss_rotation.item()
        loss_linearity_average_loss += linearity_loss.item()

        rotation_encoding_change_on_position_avg += rotation_encoding_change_on_position.item()
        rotation_encoding_change_on_rotation_avg += rotation_encoding_change_on_rotation.item()

        position_encoding_change_on_position_avg += position_encoding_change_on_position.item()
        position_encoding_change_on_rotation_avg += position_encoding_change_on_rotation.item()

        if pretty_print:
            pretty_display(epoch % epoch_print_rate)

        if epoch % epoch_print_rate == 0 and epoch != 0:

            epoch_average_loss /= epoch_print_rate
            reconstruction_average_loss /= epoch_print_rate
            loss_same_position_average_loss /= epoch_print_rate
            loss_same_rotation_average_loss /= epoch_print_rate
            loss_ratio_position_average_loss /= epoch_print_rate
            loss_ratio_rotation_average_loss /= epoch_print_rate
            loss_linearity_average_loss /= epoch_print_rate

            rotation_encoding_change_on_position_avg /= epoch_print_rate
            rotation_encoding_change_on_rotation_avg /= epoch_print_rate

            position_encoding_change_on_position_avg /= epoch_print_rate
            position_encoding_change_on_rotation_avg /= epoch_print_rate

            # Print average loss for this epoch
            print("")
            print(f"EPOCH:{epoch}/{num_epochs} ")
            print(
                f"RECONSTRUCTION LOSS:{reconstruction_average_loss} | LOSS SAME POSITION:{loss_same_position_average_loss} | LOSS SAME ROTATION:{loss_same_rotation_average_loss} | RATIO LOSS POSITION:{loss_ratio_position_average_loss} | RATIO LOSS ROTATION:{loss_ratio_rotation_average_loss} | LINEARITY LOSS:{loss_linearity_average_loss}")
            print(
                f"Changes of rotation encoding on position: {rotation_encoding_change_on_position_avg} | Changes of rotation encoding on rotation: {rotation_encoding_change_on_rotation_avg}")
            print(
                f"Changes of position encoding on position: {position_encoding_change_on_position_avg} | Changes of position encoding on rotation: {position_encoding_change_on_rotation_avg}")

            print(f"AVERAGE LOSS:{epoch_average_loss}")
            print("--------------------------------------------------")

            epoch_average_loss = 0
            reconstruction_average_loss = 0
            loss_same_position_average_loss = 0
            loss_same_rotation_average_loss = 0
            loss_ratio_position_average_loss = 0
            loss_ratio_rotation_average_loss = 0
            loss_linearity_average_loss = 0

            if pretty_print:
                pretty_display_reset()
                pretty_display_start(epoch)

    return abstraction_block


def run_abstraction_block_exploration_until_threshold(abstraction_network: AbstractionBlockImage,
                                                      storage: StorageSuperset2,
                                                      threshold_reconstruction) -> AbstractionBlockImage:
    # TODO: Implement exit clause in training
    # abstraction_network = _train_autoencoder_abstraction_block(abstraction_network, storage, 10000, True)
    return abstraction_network


def run_abstraction_block_exploration(abstraction_network: AbstractionBlockImage,
                                      storage: StorageSuperset2) -> AbstractionBlockImage:
    abstraction_network = _train_autoencoder_abstraction_block(abstraction_network, storage, 7500, True)
    return abstraction_network
