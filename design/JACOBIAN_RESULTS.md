# Base-frame J0 and singular positions

The saved pose is nonsingular for both XYZ positioning and the arm's five joint motions. The gripper opening is excluded from the five-column arm Jacobian.

This check uses the actual FreeCAD frame placements and the fixed nominal grip-centre marker `(15,61,3)` in the gripper frame. The marker is between the closed fingertips; it does not follow the pads as the gripper opens. World Z includes the 8 mm desk adapter. Switching to the chassis adapter lowers the listed Z positions by 2 mm, without changing ranks.

| Configuration | Joint output angles, degrees: yaw / shoulder / elbow / wrist pitch / roll | TCP world XYZ, mm | XYZ rank / 3 | Arm rank / 5 |
| --- | --- | --- | --- | --- |
| Saved home | 0 / 55 / -65 / 20 / 0 | 335.138 / 27.000 / 261.763 | 3 | 5 |
| Straight elbow | 0 / 55 / 0 / 20 / 0 | 150.424 / 27.000 / 469.819 | 3 | 4 |
| XYZ singular example | 0 / 85 / 30 / -29.0421865045 / -29.0546040991 | 0.000 / 30.887 / 493.934 | 2 | 5 |
| All joint angles zero, mathematical reference | 0 / 0 / 0 / 0 / 0 | 384.000 / 27.000 / 168.000 | 3 | 4 |

The all-zero reference is outside the shoulder slider range. The XYZ singular example lies inside the slider ranges, but its physical clearance has not been checked. Rounded input angles may produce a near singular rather than exactly singular result.

## Meaning of zero Jacobian

For revolute joint i, the base-frame geometric column is `[a_i × (p_TCP - o_i); a_i]`, using its axis direction `a_i` and origin `o_i` in world coordinates. Thus `J0` is 6 × 5. Its determinant is undefined. Singularity means `rank(J0)<5`; for XYZ-only control it means `rank(Jv)<3`, where `Jv` is the top three rows. Equivalently the corresponding Gram determinant vanishes. SVD is used for the actual numerical decision, with relative rank tolerance 1e-8.

At elbow zero, the three parallel pitch-axis origins are collinear, making their columns linearly dependent. XYZ can still retain rank 3 because of the offset tool and wrist roll. At the XYZ singular example, the world-Y row of Jv vanishes: no instantaneous joint motion can translate the reference point in world Y. The full Jacobian can nevertheless retain rank 5 because orientation motion remains available.

At home, the unscaled base-frame Jacobian is:

```text
                 yaw   shoulder     elbow  wrist pitch     roll
vx           -27.0000  -118.7626   -40.9431   -55.7032    -4.6885
vy           335.1378     0.0000     0.0000     0.0000   -15.0000
vz             0.0000   310.1378   255.6480   171.9394    26.5898
wx             0.0000     0.0000     0.0000     0.0000     0.9848
wy             0.0000    -1.0000    -1.0000    -1.0000     0.0000
wz             1.0000     0.0000     0.0000     0.0000     0.1736
```

Linear rows are mm per radian of joint-output motion; angular rows are rad/rad. For servo-command angles, multiply the shoulder column by -0.5 because `ShoulderServoCommand = 90 - 2*(ShoulderPitch - 55)`. This nonzero scaling preserves rank.

Linear rows are divided by 359 mm before comparing full singular values or condition numbers, to make the length/angular weighting explicit. Home has minimum scaled full singular value 0.10849 and condition number 19.68. With the other straight-elbow example angles fixed, an elbow angle of 1 degree gives condition number 1246; at 0.1 degree it reaches 12455. Numerical rank is restored away from zero, but velocity inversion becomes poorly conditioned.

## Use in FreeCAD

Run **JacobianCheck.FCMacro** to check the current live pose without moving it. Alternatively rerun **MoveArm.FCMacro**: its updated panel reports XYZ and arm ranks after each slider change and provides a **Jacobian details** button. The near-singular panel warning at scaled condition number >200 is a heuristic, not a certified control limit.

`jacobian_check.json` contains all matrices, singular values and verification errors. `jacobian_positions.csv` lists the checked positions. `check_jacobian.py` reproduces the check using FreeCAD's bundled Python. The analytical Jacobian was checked against central finite differences for linear and angular velocity, and its TCP positions against FreeCAD's native expression-driven hierarchy at six configurations. The check reads the saved CAD without saving any pose changes. It is not an exhaustive singularity, collision, load or joint-limit validation.
