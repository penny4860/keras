# -*- coding: utf-8 -*-

import numpy as np
import cv2
import matplotlib.pyplot as plt
import argparse

from keras.models import Model
from keras.applications.resnet50 import ResNet50, preprocess_input \
    as resnet_preprocess
from keras.applications.inception_resnet_v2 \
    import InceptionResNetV2, preprocess_input \
    as inception_resnet_preprocess
from keras.applications.nasnet import NASNetLarge, preprocess_input \
    as nasnet_preprocess
from keras.layers import UpSampling2D, Conv2D


N_CLASSES = 1000

# python main.py dog.png resnet
parser = argparse.ArgumentParser(
    description='Class Activation Mapping with Keras.')
parser.add_argument('input_image_file', metavar='image', type=str,
                    help='Input image file path.')
parser.add_argument('base_network', metavar='base', type=str,
                    default="resnet50",
                    help='Base network model for Class Activation Mapping.')

args = parser.parse_args()


class _Backend(object):
    def __init__(self,
                 input_size,
                 last_conv_layer,
                 pred_layer,
                 preprocess_fn,
                 model_class):
        self.input_size = input_size
        self.preprocess_fn = preprocess_fn
        self.cam_model = self._create_cam_model(
            model_class, last_conv_layer, pred_layer)

    def load_img(self, fname):
        original_img = cv2.imread(fname)[:, :, ::-1]
        original_size = (original_img.shape[1], original_img.shape[0])
        img = cv2.resize(original_img, (self.input_size, self.input_size))
        imgs = np.expand_dims(self.preprocess_fn(img), axis=0)
        return imgs, original_img, original_size

    def predict(self, imgs):
        preds, cams = self.cam_model.predict(imgs)
        return preds, cams

    def _create_cam_model(self, model_class, last_conv_layer, pred_layer):
        model = model_class(input_shape=(self.input_size, self.input_size, 3))

        final_params = model.get_layer(pred_layer).get_weights()
        final_params = (final_params[0].reshape(
            1, 1, -1, N_CLASSES), final_params[1])

        last_conv_output = model.get_layer(last_conv_layer).output
        x = UpSampling2D(size=(32, 32), interpolation="bilinear")(
            last_conv_output)
        x = Conv2D(filters=N_CLASSES, kernel_size=(
            1, 1), name="predictions_2")(x)

        cam_model = Model(inputs=model.input,
                          outputs=[model.output, x])
        cam_model.get_layer("predictions_2").set_weights(final_params)
        return cam_model


class BackendInceptionResNetV2(_Backend):
    def __init__(self):
        super(
            BackendInceptionResNetV2,
            self).__init__(
            input_size=299,
            last_conv_layer="conv_7b_ac",
            pred_layer="predictions",
            preprocess_fn=inception_resnet_preprocess,
            model_class=InceptionResNetV2)


class BackendResNet50(_Backend):
    def __init__(self):
        super(BackendResNet50, self).__init__(input_size=224,
                                              last_conv_layer="activation_49",
                                              pred_layer="fc1000",
                                              preprocess_fn=resnet_preprocess,
                                              model_class=ResNet50)


class BackendNASNetLarge(_Backend):
    def __init__(self):
        super(
            BackendNASNetLarge,
            self).__init__(
            input_size=331,
            last_conv_layer="activation_260",
            pred_layer="predictions",
            preprocess_fn=nasnet_preprocess,
            model_class=NASNetLarge)


def postprocess(preds, cams, top_k=1):
    idxes = np.argsort(preds[0])[-top_k:]
    class_activation_map = np.zeros_like(cams[0, :, :, 0])
    for i in idxes:
        class_activation_map += cams[0, :, :, i]
    return class_activation_map


if __name__ == "__main__":

    # 1. create keras-cam model
    if args.base_network == "resnet":
        cam_builder = BackendResNet50()
    elif args.base_network == "nasnet":
        cam_builder = BackendNASNetLarge()
    elif args.base_network == "inception":
        cam_builder = BackendInceptionResNetV2()
    else:
        raise ValueError(
            "The base network should be one of resnet, nasnet, or inception.")

    # 2. load image
    imgs, original_img, original_size = cam_builder.load_img(
        args.input_image_file)

    # 3. run model
    preds, cams = cam_builder.predict(imgs)

    # 4. postprocessing
    class_activation_map = postprocess(preds, cams)

    # 5. plot image+cam to original size
    plt.imshow(original_img, alpha=0.5)
    plt.imshow(cv2.resize(class_activation_map,
                          original_size), cmap='jet', alpha=0.5)
    plt.show()
