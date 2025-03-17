# ava: Tool to Understand Mobile Video Codecs

# 1. Introduction

ava is a tool that allows understanding mobile video codecs (both encoders and decoders). It works on both hardware and software encoders.

Ava can do:
* List advertised encoder features.
* Check actual support for different encoder features (either advertised or not) by analyzing the bitstream structure.
* Calculate RD-curves, which measure encoder quality as a function of bitrate (based on a dataset).

The ideal use case for ava is to design a test suite

Some ava goals:
* (1) easy to run: We should be able to define the test or test suite we want to run using a very simple set of instructions. This would allow directing a third-party to run the tests.
* (2) reproducibility
* (3) reliability: Ava should not crash without a clear message that can be reported easily.



